#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar  6 09:28:14 2020

@author: ishashah
"""
import os
import re
import numpy as np
import pandas as pd
import requests
import lxml
import ftfy
from bs4 import BeautifulSoup
from datetime import datetime
from time import sleep
import urllib.request
import logging
import sys


PLAIN_TEXT_PATH = '/Users/ishashah/Documents/DFG/clean_text/'
INDEX_PATH = 'www.sec.gov/Archives/edgar/full-index/'
#GET_QUARTERS = ['/2016/QTR4/', '/2017/QTR1/', '/2017/QTR2/', '/2017/QTR3/']
# GET_QUARTERS = ['/2017/QTR4/', '/2018/QTR1/', '/2018/QTR2/', '/2018/QTR3/']
GET_QUARTERS = ['/2018/QTR4/', '/2019/QTR1/', '/2019/QTR2/', '/2019/QTR3/']

def get_logger():
    t = datetime.now().strftime('%m%d-%H%M')
    logger = logging.getLogger()
    ch = logging.StreamHandler()
    fh = logging.FileHandler(f'log_{t}.txt')
    formatter = logging.Formatter('%(asctime)s: %(message)s', datefmt='%H:%M:%S')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)
    logger.addHandler(ch)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)
    return logger


def parse_company_index(req):
    lines = req.text.split('\n')
    HEADER_LINE = 8
    COL_BREAKS = [62, 74, 86, 98, 120]
    ret = []
    for i in range(HEADER_LINE+2, len(lines)-1):
        line_list = []
        line_list.append(lines[i][:COL_BREAKS[0]].rstrip())
        line_list.append(lines[i][COL_BREAKS[0]:COL_BREAKS[1]].rstrip())
        line_list.append(lines[i][COL_BREAKS[1]:COL_BREAKS[2]].rstrip())
        line_list.append(lines[i][COL_BREAKS[2]:COL_BREAKS[3]].rstrip())
        line_list.append(lines[i][COL_BREAKS[3]:].rstrip())
        ret.append(line_list)
    columns = ['company', 'form_type', 'cik', 'date_filed', 'link']
    return pd.DataFrame(ret, columns=columns)


def get_annual_filings_df():
    logger.info('retrieving filings index...')
    out = []
    for quarter in GET_QUARTERS:
        logger.info(quarter)
        r = requests.get('https://' + INDEX_PATH + quarter + 'company.idx')
        idx_df = parse_company_index(r)
        out.append(idx_df)
    full_company_index = pd.concat(out, axis=0).reset_index(drop=True)
    full_company_index.cik = full_company_index.cik.astype(np.int64)
    full_company_index['accession_number'] = full_company_index.link.apply(lambda x: x.split('/')[-1].split('.')[0])

    # https://www.sec.gov/include/ticker.txt
    CIK_TICKER_LOOKUP_PATH = 'https://www.sec.gov/include/ticker.txt'
    cik_ticker = pd.read_csv(CIK_TICKER_LOOKUP_PATH, sep='\t', header=None, names=['ticker', 'cik'])
    # sics = pd.read_csv('./data/sics_new.csv',
    #                    usecols=['company_ticker', 'company_name', 'primary_industry_id', 'scope', 'is_active'])
    # sics = sics[(sics.scope == 'US') & (sics.is_active == 'Y')]

    full_company_index = pd.merge(full_company_index, cik_ticker, left_on="cik", right_on="cik", how='left')
    full_company_index.ticker = full_company_index.ticker.fillna('_UNK')
    full_company_index.ticker = full_company_index.ticker.str.upper()

    # full_company_index = pd.merge(full_company_index, sics, left_on="ticker", right_on="company_ticker", how='left')
    # full_company_index.drop(['company_ticker', 'company_name'], axis=1, inplace=True)

    annual_filings = full_company_index[full_company_index.form_type.isin(['DEF 14A'])]
    # , 'DEFA14A', 'PRE 14A', 'DEFM14A'
    # annual_filings = annual_filings[annual_filings.primary_industry_id.notna()]
    logger.info(f'annual filings: {len(annual_filings)}')
    return annual_filings


def scrape_filing(link, ticker, form_type):
    url_prefix = "https://www.sec.gov/Archives/"
    file = urllib.request.urlopen(url_prefix + link)
    out = ''
    in_doc = False
    i = 0
    while True:
        i += 1
        line = file.readline().decode('utf-8', 'ignore')
        if line.startswith("CONFORMED PERIOD OF REPORT"):
            por = line.split(':')[-1].strip()
        if line.startswith("<TEXT>"):
            in_doc = True
        if in_doc:
            # bs4/lxml handles <br>s by simply removing them, which squashes words
            # replace <br>s with spaces before passing to bs4
            cleanline = re.sub(r'<br>|<BR>', ' ', line)
            out += cleanline + ' '
        if line.startswith("</TEXT>"):
            break
    return BeautifulSoup(out, 'lxml'), por


def parse_soup(soup, base_element='p', is_xbrl=False):
    out = []
    base_els = soup.find_all(base_element)

     # for iXBRL, the first <div> is a large metadata block, so skip it
    if is_xbrl: base_els = base_els[1:]

    n_base_els = len(base_els)

    i = 0
    in_table = False
    while i < n_base_els:
        el = base_els[i]

        # skip divs that contain other divs or tables to avoid recursion
        # i.e. divs that contain divs would otherwise appear twice
        descendants = [d.name for d in el.descendants]
        if base_element in descendants or 'table' in descendants:
            i += 1
            continue

        if el.parent.name != 'td': # ordinary line
            if in_table:
                out.append('[END TABLE]')
                out.append('\n')
                in_table = False
            # remove line breaks inside elements (iXBRL filings)
            out.append(el.text.replace('\n', ''))
            i += 1
            continue

        # loop through tables row-wise
        elif el.parent.name == 'td':
            if not in_table:
                out.append('[BEGIN TABLE]')
                in_table = True
            row_el = el.parent.parent
            # handling for poorly-formed table markup
            if row_el.name != 'tr': break

            # sometimes text is contained directly in <td>s without <div>s or <p>s inside
            # so search on <td> instead
            row_tds = row_el.find_all('td')

            n_tds = len(row_tds)
            row_text = ''
            for el in row_tds:
                # Tables in most annual filings contain tds with a single text element.
                # Some tables have <td>s containing multiple <div>s, which would otherwise
                # become squashed into a single string without spaces between words...
                if len(el.find_all('div')) >1:
                    row_text += ' '.join([e.text for e in el.find_all('div')])
                else:
                    # iXBRL filings often contain extra line breaks in text elements:
                    row_text += el.text.replace('\n', ' ') + ' '
                # since the row-wise loop is searching for <tr> elements, we only increment
                # if the <tr> contains the base_element (i.e. <div> or <p>), in order to keep
                # the counter i in sync with the base_els iterable
                if base_element in [e_.name for e_ in el.children]:
                    i += 1
            out.append(row_text)

    return ('\n').join(out)


def get_filing_text(soup):
    n_p = len(soup.find_all('p'))
    n_div = len(soup.find_all('div'))
    n_span = len(soup.find_all('span'))

    # if there are <span>s, the file is probably iXBRL.
    if n_span > n_p: return parse_soup(soup, 'div', is_xbrl=True)

    # if not iXBRL, use <p> or <div>, whichever is more abundant in the markup
    elif n_p > n_div: return parse_soup(soup, 'p', is_xbrl=False)
    else: return parse_soup(soup, 'div', is_xbrl=False)


def get_clean_text(str_in):
    ret = str_in
    ret = re.sub(r'\x9f', '•', ret) # used as bullet in 0000004904-19-000009
    ret = ftfy.fix_text(ret)
    ret = re.sub(r'\xa0', ' ', ret) # remove \xa0

    # remove page breaks
    ret = re.sub(r'\s+(-\s*\d+\s*-\s*)+\s*(Table of Contents\s*)+\s*\n', '\n', ret) # e.g. 0001178879-19-000024
    ret = re.sub(r'\s*\d+(\s*Table of Contents\n)+\n', ' ', ret) # e.g. 0000764180-19-000023
    ret = re.sub(r'\s*(\d+\n)+\s*\n\n', ' ', ret) # e.g. 0000824142-19-000040
    ret = re.sub(r'\n\s*\d+\s*\n', ' ', ret) # base case: digits separated by line breaks

    # U+2022, U+00B7, U+25AA, U+25CF, U+25C6
    ret = re.sub(r'([•·▪●◆])\s*\n', '\1 ', ret) # combine orphaned bullet chars separated from text by newline
    ret = re.sub(r'([•·▪●◆])(\w)', r'\1 \2', ret) # separate bullets squished next to text
    ret = re.sub(r'[ ]*([•·▪●◆])[ ]*', r'\1 ', ret) # consolidate whitespace around bullets

    # not active in order to preserve visual structure of multi-level bulleted lists
    #ret = re.sub(r'[•·▪●◆]', '•', ret) # use single bullet char

    # join orphaned sentences (line starts with a lower-case word)
    ret = re.sub(r'([a-z\,])\s*\n\s*([a-z])', r'\1 \2', ret)

    # fix table delimiters not separated by newline
    ret = re.sub(r'\[END TABLE\](.)', r'[END TABLE]\n\1', ret)
    ret = re.sub(r'(.)\[BEGIN TABLE\]', r'\1\n[BEGIN TABLE]', ret)

    # remove empty tables
    ret = re.sub(r'\[BEGIN TABLE\]s*\n\s*\[END TABLE\]', r'\n', ret)

    # remove table delmiters if table has only one row
#    ret = re.sub(r'\[BEGIN TABLE\]\s*\n([^\n]+)\n\s*\[END TABLE\]', r'\1', ret)

    ret = re.sub(r'(\d)\s*\)', r'\1)', ret)
    ret = re.sub(r'\s*%', r'%', ret)

    ret = re.sub(r'\n\s*\n', r'\n', ret) # remove empty lines

    return ret


def convert_to_plain_text(df):
    # scrape and parse filings in the DataFrame; save as plain text
    n_rows = df.shape[0]
    for i, row in enumerate(df.iterrows()):
        ticker = row[1].ticker
        accession_num = row[1].accession_number
        form_type = row[1].form_type
        soup, por = scrape_filing(row[1].link, ticker, form_type)
        text = get_filing_text(soup)
        text = get_clean_text(text)
        new_fname = f'{ticker}_{form_type}_{por}_{accession_num}.txt'
        try:
          with open(PLAIN_TEXT_PATH + new_fname, 'w', encoding='utf-8') as f:
              f.write(text)
              f.close()
          logger.info(f'{i+1}/{n_rows} {new_fname}')
        except:
          print("Skipped:",sys.exc_info()[0],"occured.")
          
if __name__ == '__main__':
    logger = get_logger()
    annual_filings = get_annual_filings_df()
    convert_to_plain_text(annual_filings)



