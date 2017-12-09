import os
import pickle

import math

from storage.database_wrapper import FileAttributeTableWrapper
from storage.text_handling import TextUtils


def get_id_url(descr_file):
    urls = {}
    with open(os.path.join(descr_file), 'r', encoding='utf-8') as file_descr:
        for line in file_descr:
            url, file_name = line.strip().split('\t')
            hash_value = file_name.split('_')[-1]
            urls[hash_value] = url
    return urls


def get_doc_ids(doc_info_list):
    ids = set()
    for doc_info in doc_info_list:
        ids.add(doc_info.id)
    return ids


def gather_info(query_info):
    docs = {}
    for word in query_info:
        for word_doc_info in query_info[word]:
            if word_doc_info.id not in docs:
                docs[word_doc_info.id] = {}
            docs[word_doc_info.id][word] = word_doc_info.count
    return docs


def process(query, lock, checkpoint_path, descr_file):
    # TODO: check & debug
    lock.acquire()
    with open(checkpoint_path, 'rb') as check_file:
        crawler_loaded = pickle.load(check_file)
        _, _, _, inv_index = crawler_loaded
    lock.release()

    preprocessed_query = TextUtils.handle(query)
    query_info = {}
    for word in preprocessed_query:
        lock.acquire()
        word_doc_info_list = inv_index.get_index(word)
        lock.release()
        query_info[word] = word_doc_info_list

    tf = gather_info(query_info)  # td[doc][word]
    urls = get_id_url(descr_file)
    cnt_docs = len(urls)
    idf = dict([(word, math.log(1.0*cnt_docs/len(query_info[word]))) for word in query_info]) # idf[word]
    docs = gather_info(query_info)

    score = {}  # BM25

    paf = FileAttributeTableWrapper()

    k1 = 1.5  # TODO: const to config
    b = 0.75

    for doc in docs:
        score[doc] = 0
        url = urls[doc]
        if '&date=' in url or '&version=mobile' in url or '?source=menu' in url:
            continue
        _, _, doc_dl, _, _ = paf.get_row(doc)
        dl_av = paf.get_average()  # TODO: Want faster
        for word in preprocessed_query:
            if word in tf[doc]:
                tf_doc_word = tf[doc][word]
            else:
                tf_doc_word = 0
            score[doc] += 1.0*idf[word]*(k1 + 1)*tf_doc_word/(k1*((1 - b) + 1.0*b*doc_dl/dl_av) + tf_doc_word)

    if len(score) == 0:
        print("Can't find anything for query {}".format(query))

    ranking_docs = sorted(score, key=score.get, reverse=True)
    for i in range(min(10, len(ranking_docs))):
        url = urls[ranking_docs[i]]
        print(url)