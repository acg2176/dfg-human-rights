# dfg-human-rights
This is the work I completed on a Data for Good Project with the Data Science Institute at Columbia University.


Goal of this Project:
The Extension project was founded to improve upon the standards set by the Sustainability Accounting Standards Board, specifically surrounding the following standards:
1. General Issue Categories of the Human Capital Management dimension
2. Supply Chain Management GIC of the Business Models and Innovation dimension



Data:
1. For unsupervised learning: SEC filings (Def 14As) were scraped using BeautifulSoup from the EDGAR database. These were proxy statements ranging from Q4 of 2018 to Q3 of 2019.
2. For supervised learning: A 10-K labeled Dataset (labeled relevant or not relevant disclosure) was given by SASB specifically for the Human Capital Management Dimension.

Preprocessing:

Proxy statements were parsed by paragraph, removing all excerpts shorter than 300 characters and duplicate paragraphs.

Word2Vec was used to train word embeddings on the dataset. Embeddings were used to create 300-dimensional vectors for each word. The vectors were averaged for each word in the excerpt to create a single representation for each excerpt.

Methods:
1. Unsupervised Learning: This was used on proxy statements to investigate new areas of existing and new materiality, and provide a foundation to label proxy statements.

a. K-Means Clustering model was used as it has been commonly used for text clustering. An elbow plot was used to determine the optimal numbers of clusters. The goal is to find intelligible clusters that could potentially be labeled relevant to human capital/human rights.

Notebook: ```word2vec_to_kmeans_SASB.ipynb```

b. (First attempt) TF-IDF was initially used as a pre-processing step as an iterative process to eliminate irrelevant/unintelligible clusters.

Notebook: ```K_Means_Clustering_Script.ipynb```

2. Supervised Learning: This was used to flag and measure instances of risk disclosure for all General Issue Categories (GICs) of the Human Capital Management dimension, and the Supply Chain Management GIC of the Business Models and Innovation dimension by firms in industries for which those categories were not considered material for SASB's 2018 standards.

a. A Logistic Regression model was trained to classify whether a 10-K excerpt is relevant to labor or not. Maximizing recall and precision is the metric of choice in order for the model to capture all positive cases. This was tuned using GridSearchCV. This would be applied to a broader corpus (in terms of both industries covered and time period) of new 10-Ks from firms in both industries that were and were not suggested to disclose on human capital and supply chain metrics according to the 2018 standards.

Notebook: ```logistic_reg-SASB.ipynb```


