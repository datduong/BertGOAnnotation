
import pickle, gzip, os, sys, re
import random
from random import shuffle
import numpy as np
import pandas as pd


GOBPterm = pd.read_csv("deepgo.bp.csv",dtype=str,header=None)
GOCCterm = pd.read_csv("deepgo.cc.csv",dtype=str,header=None)
GOMFterm = pd.read_csv("deepgo.mf.csv",dtype=str,header=None)

GOname = list(GOBPterm[0]) + list(GOMFterm[0]) + list(GOCCterm[0])
GOnum = len(GOname)

GO_as_vocab = {}
for index,val in enumerate(GOname): 
  GO_as_vocab[index] = val


## insert the GO as a vocab
vocab_bert = pd.read_csv("/u/scratch/d/datduong/BERTPretrainedModel/cased_L-12_H-768_A-12Kmer/vocab+3kmer.txt",dtype=str,sep="\t",header=None)
total_vocab = vocab_bert.shape[0]
vocab_bert.iloc[(total_vocab-GOnum):total_vocab] = np.reshape( np.array(GOname), (GOnum,1) ) 

vocab_bert.to_csv("/u/scratch/d/datduong/BERTPretrainedModel/cased_L-12_H-768_A-12Kmer/vocab+3kmer+GO.txt",index=None,header=None)

