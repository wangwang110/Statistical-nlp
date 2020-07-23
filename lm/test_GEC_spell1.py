# encoding=utf-8
from __future__ import division
import math
import nltk
# import cPickle
import pickle
import numpy as np
import distance
import lcs
import time
# from pattern.en import lemma
from nltk.corpus import wordnet


### only for false word error

class LangModel:
    def __init__(self, order, alpha, sentences):
        self.index = 0
        self.order = order
        self.alpha = alpha
        if order > 1:
            self.backoff = LangModel(order - 1, alpha, sentences)
            self.lexicon = None
        else:
            self.backoff = None
            self.n = 0

        self.ngramFD = nltk.FreqDist()
        lexicon = set()
        # set NUll
        for sentence in sentences:
            self.index += 1
            words = sentence.split(" ")
            wordNGrams = nltk.ngrams(words, order)
            for wordNGram in wordNGrams:
                self.ngramFD[wordNGram] += 1
                if order == 1 and wordNGram[0] != "<s>" and wordNGram[0] != "</s>":
                    lexicon.add(wordNGram)
                    self.n += 1
        self.v = len(lexicon)

    def logprob(self, ngram):
        t = self.prob(ngram)
        return math.log(t)

    def prob(self, ngram):
        current = self
        while current.order > len(ngram):
            current = current.backoff
        if current.backoff != None:

            freq = current.ngramFD[ngram]
            backoffFreq = current.backoff.ngramFD[ngram[:-1]]
            if freq == 0:
                if len(ngram) > 1:
                    backprob = current.backoff.prob(ngram[1:])
                    return current.alpha * backprob
                else:
                    backprob = current.backoff.prob(ngram)
                    return current.alpha * backprob

            else:
                if backoffFreq > 0:
                    return freq / backoffFreq
                else:
                    return freq / current.n
        else:
            k = float(float(current.ngramFD[ngram] + 1) / float(current.n + current.v))
            return k


def get_log_prob(words, lm=None):
    logprob = lm.logprob(tuple(words)) * -1
    ## log1==0
    ## 值越大，越不是合理的词
    return logprob


def get_raw_prob(words, lm=None):
    prob = lm.prob(tuple(words))
    return prob


def sentence_log_prob(words, lm=None):
    ##获取一个句子中，所有的ngram概率返回一个list
    logprobs = []
    if (len(words) <= n_gram):
        ##开始的几个单词，不够ngram个词，特殊处理
        logprobs.append(get_log_prob(words, lm))
    else:
        wordngrams = nltk.ngrams(words, n_gram)
        for wordTrigram in wordngrams:
            logprobs.append(get_log_prob(wordTrigram, lm))
    return logprobs


def load_model():
    return pickle.load(open("lm3.bin", 'r'))


start = time.time()
lm1 = load_model()
print("load model time", time.time() - start)
replace_threshold = 0.3
n_gram = 5

s = open('candidates.pkl', 'r')
wrong_sample = open("wrowg_sample.txt", "w")
candidates = pickle.load(s)


##离线计算的候选值文件，在save_candidates.py中计算


def get_lexicon_list(path):
    word_list = []
    file_object = open(path)
    for line in file_object:
        line = line.strip().replace("\n", "").replace("\r", "")
        word_list.append(line)
    return word_list


def splitSentence(paragraph):
    ## nltk自带的分句文件，以句号分
    tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
    sentences = tokenizer.tokenize(paragraph)
    return sentences


def get_candidates(word):
    ## 获取一个词的候选集列表，根据分值

    candidates_words = []

    if word not in candidates.keys():
        ## 词不在离线计算的文件中，重新计算加入

        edits1 = distance.edits1(word)
        edits2 = distance.edits2(word)

        temp = open('f2true.pkl', 'rb')
        f2true = pickle.load(temp)
        if word in f2true:
            edits1 = edits1 | set(f2true[word])

        dist1, dist2 = distance.known(edits1), distance.known(edits2)
        dist2 = dist2 - dist1 & dist2

        dist1 = list(dist1)
        dist2 = list(dist2)

        for w in dist1:
            candidates[word].append(
                (w, 1, lcs.find_lcsubstr(w, word) / len(word), lcs.find_lcseque(w, word) / len(word)))
        for w in dist2:
            candidates[word].append(
                (w, 0.5, lcs.find_lcsubstr(w, word) / len(word), lcs.find_lcseque(w, word) / len(word)))

    for temp in candidates[word]:
        if len(word) <= 1:
            continue
        elif len(word) == 2 and temp[1] == 0.5:
            continue
            # 编辑距离大于word长度，不作为候选词
        score = temp[1] * 2 + 0.9 * temp[2] + 0.5 * temp[3]

        if (temp[0][0] != word[0]):
            ##首字母相同
            score = 0.5 * score

        if (score > 2):
            candidates_words.append((temp[0], score))

    return candidates_words


def replace(words, index, isTrue=False):
    original_word = words[index]
    ## replace(sentence,words[i],i)

    candidates_words = get_candidates(words[index])

    if (len(candidates_words) == 0):
        ##没有候选单词返回原有的单词，不改
        return original_word

    candidate_probs = {}
    start = max(0, index - n_gram + 1)
    end = min(len(words) - 1, index + n_gram)
    ##避免越界

    for word in candidates_words:
        words[index] = word[0]
        ##替换原词为候选词，计算概率
        temp = words[start:end]
        logprobs = sentence_log_prob(temp, lm1)
        candidate_probs[word[0]] = np.mean(logprobs) - word[1]
        # print (np.mean(logprobs)+1)*word[1]
        ###求和也可以

    result = min(candidate_probs.items(), key=lambda s: s[1])
    # (key,value)

    return result[0]


def process_txt(path):
    punctuations = [',', '(', ')', '.', '!', '"', '?', 'st', 'ed']

    dictionary_object = open('dictionary_youdao_1.txt')
    dictionary = []
    for line in dictionary_object:
        line = line.strip().replace("\n", "").replace("\r", "")
        dictionary.append(line)

    list_sentence = []
    with open(path) as f:
        for line in f.readlines():
            list_sentence.append(line.strip())

    result_file = open('result_spell_ngram_rule.txt', 'w')

    sentences_num = len(list_sentence)
    for j in range(sentences_num):
        print(j)

        sentence = list_sentence[j]
        list_sentence_word = sentence.split(" ")
        # nltk.word_tokenize(sentence)
        # 注意分词工具会根据空格和标点分
        i = 0
        for temp_word in list_sentence_word:
            temp_word_lemma = temp_word
            if temp_word_lemma not in punctuations and temp_word_lemma not in dictionary:
                correct_word = replace(list_sentence_word, i, False)
                list_sentence_word[i] = correct_word

                # else:
                #     correct_word = replace(list_sentence_word, i, args, sess, False)
            i = i + 1
        result_file.write(" ".join(list_sentence_word) + "\n")
    result_file.close()


if __name__ == '__main__':
    path = './confuse.txt'
    process_txt(path)
