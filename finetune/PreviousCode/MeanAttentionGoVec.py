# coding=utf-8
# Copyright 2018 The Google AI Language Team Authors and The HuggingFace Inc. team.
# Copyright (c) 2018, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Fine-tuning the library models for language modeling on a text file (GPT, GPT-2, BERT, RoBERTa).
GPT and GPT-2 are fine-tuned using a causal language modeling (CLM) loss while BERT and RoBERTa are fine-tuned
using a masked language modeling (MLM) loss.
"""

from __future__ import absolute_import, division, print_function

import argparse
import glob
import logging
import os
import pickle
import random
import re,sys
import pandas as pd

import numpy as np

from scipy.sparse import coo_matrix

import torch
from torch.utils.data import DataLoader, Dataset, SequentialSampler, RandomSampler
from torch.utils.data.distributed import DistributedSampler
from tensorboardX import SummaryWriter
from tqdm import tqdm, trange

from pytorch_transformers import (WEIGHTS_NAME, AdamW, WarmupLinearSchedule,
                  BertConfig, BertForMaskedLM, BertTokenizer,
                  GPT2Config, GPT2LMHeadModel, GPT2Tokenizer,
                  OpenAIGPTConfig, OpenAIGPTLMHeadModel, OpenAIGPTTokenizer,
                  RobertaConfig, RobertaForMaskedLM, RobertaTokenizer)

from pytorch_transformers.modeling_bert import BertForPreTraining

logger = logging.getLogger(__name__)

sys.path.append("/local/datdb/BertGOAnnotation")
import KmerModel.TokenClassifier as TokenClassifier
import evaluation_metric
import PosthocCorrect


MODEL_CLASSES = {
  'ppi': (BertConfig, TokenClassifier.BertForTokenClassification2EmbPPI, BertTokenizer), ## replace the standard @BertForTokenClassification
  'noppi': (BertConfig, TokenClassifier.BertForTokenClassification2Emb, BertTokenizer) ## replace the standard @BertForTokenClassification
}


def ReadProtData(string,num_aa,max_num_aa,annot_data,annot_name_sorted,evaluate):

  ## must do padding so all items get the same size
  out = np.zeros((max_num_aa,len(annot_name_sorted))) ## maximum possible
  if string == 'none':
    return coo_matrix(out)

  # @string is some protein data, delim by ";"
  annot = string.split(';')
  annot_matrix = np.zeros((num_aa,len(annot))) ## exact @num_aa without CLS and SEP

  for index, a in enumerate(annot): ## we do not need the whole matrix. we can use 1,2,3,4,5 indexing style on the column entry
    ## want annotation on protein sequence into matrix. Len x Type
    ## a = 'COILED 87-172;DOMAIN uba 2-42;DOMAIN ubx 211-293'.split(';')
    a = a.split() ## to get the position, which should always be at the last part
    type_name = " ".join( a[0 : (len(a)-1)] )

    if type_name not in annot_name_sorted: ## unseen Domain Type
      type_number = 1 ## set to UNK
    else:
      ## !! notice, shift by +2 so that we PAD=0 (nothing) and UNK=1 (some unseen domain)
      type_number = annot_name_sorted[ type_name ] ## make sure we exclude position which is last. @annot_name_sorted is index-lookup

    ## in preprocessing, we have -1, because uniprot give raw number, but python starts at 0.
    ## we do not -1 for the end point.
    row = [int(f) for f in a[-1].split('-')] ## get back 2 numbers
    row = np.arange(row[0]-1,row[1]) ## continuous segment

    ## we have to randomly assign UNK... assign a whole block of UNK
    ## do not need to assign random UNK for dev or test set
    if (not evaluate) and (type_number > 1): ## chance of being UNK
      if np.random.uniform() < annot_data[type_name][1]*1.0/annot_data[type_name][0]:
        annot_matrix [ row,index ] = 1 ## type=1 is UNK
      else:
        annot_matrix [ row,index ] = type_number ## @col is the number of the type w.r.t. the whole set of types, @index is just for this string
    else:
      annot_matrix [ row,index ] = type_number

  ## out is max_len (both aa + CSL SEP PAD) + len_annot
  ## read by row, so CLS has annot=0
  ## only need to shift 1 row down
  out[1:(num_aa+1), 0:len(annot)] = annot_matrix ## notice shifting by because of CLS and SEP

  # print ('\nsee annot matrix\n')
  # print (annot_matrix)
  return coo_matrix(out)


class TextDataset(Dataset):
  def __init__(self, tokenizer, label_2test_array, file_path='train', block_size=512, max_aa_len=1024, args=None, evaluate=None, config=None):
    # @max_aa_len is already cap at 1000 in deepgo, Facebook cap at 1024

    self.args = args
    self.config = config

    assert os.path.isfile(file_path)
    directory, filename = os.path.split(file_path)
    # if config.aa_type_emb:
    #   directory = os.path.join(directory , 'aa_ppi_annot_cache')
    # else:
    #   directory = os.path.join(directory , 'aa_ppi_cache')
    directory = os.path.join(directory , args.cache_name) ## !! strictly enforce name
    if not os.path.exists(directory):
      os.mkdir(directory)

    cached_features_file = os.path.join(directory, f'cached_lm_{block_size}_{filename}')

    if os.path.exists(cached_features_file+'label1hot'): ## take 1 thing to test if it exists
      logger.info("Loading features from cached file %s", cached_features_file)
      with open(cached_features_file+'label1hot', 'rb') as handle:
        self.label1hot = pickle.load(handle)
      with open(cached_features_file+'input_ids_aa', 'rb') as handle:
        self.input_ids_aa = pickle.load(handle)
      with open(cached_features_file+'input_ids_label', 'rb') as handle:
        self.input_ids_label = pickle.load(handle)
      with open(cached_features_file+'mask_ids_aa', 'rb') as handle:
        self.mask_ids_aa = pickle.load(handle)
      with open(cached_features_file+'ppi_vec', 'rb') as handle:
        self.ppi_vec = pickle.load(handle)
      if config.aa_type_emb:
        with open(cached_features_file+'aa_type_emb', 'rb') as handle:
          self.aa_type_emb = pickle.load(handle)

    else:

      annot_name_sorted = None
      if args.aa_type_file is not None:
        print ('load in aa_type_file')
        annot_data = pickle.load ( open ( args.aa_type_file, 'rb' ) )
        temp = sorted (list (annot_data.keys() ) ) ## easiest to just do by alphabet, so we can backtrack very easily
        ## make sure we exclude position which is last. @annot_name_sorted is index-lookup, so we have +2
        annot_name_sorted = {value: index+2 for index, value in enumerate(temp)} ## lookup index


      label_2test_array = sorted(label_2test_array) ## just to be sure we keep alphabet
      num_label = len(label_2test_array)
      print ('num label {}'.format(num_label))
      label_index_map = { name : index for index,name in enumerate(label_2test_array) } ## faster look up
      # label_string = " ".join(label_2test_array)

      logger.info("Creating features from dataset file at %s", directory)

      self.label1hot = [] ## take 1 hot (should short labels by alphabet)
      self.input_ids_aa = []
      self.input_ids_label = []
      self.mask_ids_aa = []
      self.ppi_vec = [] ## some vector on the prot-prot interaction network... or something like that
      if config.aa_type_emb:
        self.aa_type_emb = []

      fin = open(file_path,"r",encoding='utf-8')
      for counter, text in tqdm(enumerate(fin)):

        # if counter > 100 :
        #   break

        text = text.strip()
        if len(text) == 0: ## skip blank ??
          continue

        ## we test all the labels in 1 single call, so we have to always get all the labels.
        ## notice we shift 1+ so that we can have padding at 0.
        # self.input_ids_label.append ( list((1+np.arange(num_label+1))) )  ## add a SEP to end of label side ??? Okay, add SEP
        self.input_ids_label.append ( np.arange(num_label).tolist() )  ## add a SEP to end of label side ??? Okay, add SEP

        ## split at \t ?? [seq \t label]
        text = text.split("\t") ## position 0 is kmer sequence, position 1 is list of labels

        ### !!!!
        ### !!!! now we append the protein-network vector
        self.ppi_vec.append ([float(s) for s in text[3].split()]) ## 3rd tab

        ## create a gold-standard label 1-hot vector.
        ## convert label into 1-hot style
        label1hot = np.zeros(num_label) ## 1D array
        this_label = text[2].strip().split() ## by space
        index_as1 = [label_index_map[label] for label in this_label]
        label1hot [ index_as1 ] = 1
        self.label1hot.append( label1hot )

        # kmer_text = text[0].split() ## !! we must not use string text, otherwise, we will get wrong len
        ## GET THE AA INDEXING '[CLS] ' + text[0] + ' [SEP]'
        this_aa = tokenizer.convert_tokens_to_ids ( tokenizer.tokenize ('[CLS] ' + text[1] + ' [SEP]') )
        len_withClsSep = len(this_aa)

        ## pad @this_aa to max len
        mask_aa = [1] * len_withClsSep + [0] * ( max_aa_len - len_withClsSep ) ## attend to non-pad
        this_aa = this_aa + [0] * ( max_aa_len - len_withClsSep ) ## padding

        if config.ppi_front: ## put ppi vector in front ... PPIvec CLS--aa--SEP GOvec ... do we need to do CLS PPIvec SEP--aa--SEP GOvec SEP ??
          if np.sum(self.ppi_vec[counter]) == 0:
            mask_value = [0] ## vector not exist, mask 0
          else:
            mask_value = [1]
          mask_aa = mask_value + mask_aa

        self.input_ids_aa.append( this_aa )
        self.mask_ids_aa.append (mask_aa)

        if config.aa_type_emb:
          ### !!! need to get token type emb of AA in protein
          ## in evaluation mode, do not need to random assign UNK
          AA = ReadProtData(text[4],len_withClsSep-2,max_aa_len,annot_data,annot_name_sorted,evaluate=evaluate)
          self.aa_type_emb.append ( AA )

        if counter < 3:
          print ('see sample {}'.format(counter))
          print (this_aa)
          print (label1hot)
          print (self.ppi_vec[counter])

        if (len(this_aa) + num_label) > block_size:
          print ('len too long, expand block_size')
          exit()

      ## save at end
      logger.info("To save read/write time... Saving features into cached file %s", cached_features_file)
      with open(cached_features_file+'label1hot', 'wb') as handle:
        pickle.dump(self.label1hot, handle, protocol=pickle.HIGHEST_PROTOCOL)
      with open(cached_features_file+'input_ids_aa', 'wb') as handle:
        pickle.dump(self.input_ids_aa, handle, protocol=pickle.HIGHEST_PROTOCOL)
      with open(cached_features_file+'input_ids_label', 'wb') as handle:
        pickle.dump(self.input_ids_label, handle, protocol=pickle.HIGHEST_PROTOCOL)
      with open(cached_features_file+'mask_ids_aa', 'wb') as handle:
        pickle.dump(self.mask_ids_aa, handle, protocol=pickle.HIGHEST_PROTOCOL)
      with open(cached_features_file+'ppi_vec', 'wb') as handle:
          pickle.dump(self.ppi_vec, handle, protocol=pickle.HIGHEST_PROTOCOL)

      if config.aa_type_emb:
        with open(cached_features_file+'aa_type_emb', 'wb') as handle:
          pickle.dump(self.aa_type_emb, handle, protocol=pickle.HIGHEST_PROTOCOL)

  def __len__(self):
    return len(self.input_ids_aa)

  def __getitem__(self, item):
    if self.config.aa_type_emb:
      return (torch.LongTensor(self.label1hot[item]),
              torch.tensor(self.input_ids_aa[item]),
              torch.tensor(self.input_ids_label[item]),
              torch.tensor(self.mask_ids_aa[item]),
              torch.tensor(self.ppi_vec[item]),
              torch.LongTensor(self.aa_type_emb[item].toarray()))
    else:
      return (torch.LongTensor(self.label1hot[item]),
              torch.tensor(self.input_ids_aa[item]),
              torch.tensor(self.input_ids_label[item]),
              torch.tensor(self.mask_ids_aa[item]),
              torch.tensor(self.ppi_vec[item]) )


def load_and_cache_examples(args, tokenizer, label_2test_array, evaluate=False, config=None):
  dataset = TextDataset(tokenizer, label_2test_array, file_path=args.eval_data_file if evaluate else args.train_data_file, block_size=args.block_size, args=args, evaluate=evaluate, config=config)
  return dataset


def set_seed(args):
  random.seed(args.seed)
  np.random.seed(args.seed)
  torch.manual_seed(args.seed)
  if args.n_gpu > 0:
    torch.cuda.manual_seed_all(args.seed)


def evaluate(args, model, tokenizer, label_2test_array, prefix="", config=None):

  num_labels = len(label_2test_array)

  # Loop to handle MNLI double evaluation (matched, mis-matched)
  eval_output_dir = args.output_dir

  eval_dataset = load_and_cache_examples(args, tokenizer, label_2test_array, evaluate=True, config=config)

  if not os.path.exists(eval_output_dir) and args.local_rank in [-1, 0]:
    os.makedirs(eval_output_dir)

  args.eval_batch_size = args.per_gpu_eval_batch_size * max(1, args.n_gpu)
  # Note that DistributedSampler samples randomly
  # eval_sampler = SequentialSampler(eval_dataset) if args.local_rank == -1 else DistributedSampler(eval_dataset)
  eval_sampler = RandomSampler(eval_dataset) if args.local_rank == -1 else DistributedSampler(eval_dataset) ## do this to avoid block of large data
  eval_dataloader = DataLoader(eval_dataset, sampler=eval_sampler, batch_size=args.eval_batch_size, num_workers=2)

  # Eval!
  logger.info("***** Running evaluation {} *****".format(prefix))
  logger.info("  Num examples = %d", len(eval_dataset))
  logger.info("  Batch size = %d", args.eval_batch_size)
  eval_loss = 0.0
  nb_eval_steps = 0
  model.eval()

  prediction = None
  true_label = None
  ave_GOvec = None

  for batch in tqdm(eval_dataloader, desc="Evaluating"):
    # batch = batch.to(args.device)

    if config.ppi_front:
      max_len_in_batch = int( torch.max ( torch.sum(batch[3][:,1::],1) ) ) ## exclude 1st column, only need max len of AA
      max_len_in_mask = max_len_in_batch + 1
    else:
      max_len_in_batch = int( torch.max ( torch.sum(batch[3],1) ) ) ## only need max len of AA
      max_len_in_mask = max_len_in_batch

    input_ids_aa = batch[1][:,0:max_len_in_batch].to(args.device)
    input_ids_label = batch[2].to(args.device) ## also pass in SEP

    attention_mask = torch.cat( (batch[3][:,0:max_len_in_mask] , torch.ones(input_ids_label.shape, dtype=torch.long) ), dim=1 ).to(args.device)

    labels = batch[0].to(args.device) ## already in batch_size x num_label
    ## must append 0 positions to the front, so that we mask out AA
    labels_mask = torch.cat((torch.zeros(input_ids_aa.shape[0], max_len_in_mask),
                             torch.ones(input_ids_label.shape)), dim=1).to(args.device)

    if args.model_type == 'ppi':
      if config.ppi_front:
        ppi_vec = batch[4].unsqueeze(1).to(args.device)
      else:
        ppi_vec = batch[4].unsqueeze(1).expand(labels.shape[0],max_len_in_batch+num_labels,256).to(args.device) ## make 3D batchsize x 1 x dim
    else:
      ppi_vec = None

    if config.aa_type_emb:
      aa_type = batch[5][:,0:max_len_in_batch,:].to(args.device)
    else:
      aa_type = None

    with torch.no_grad():
      outputs = model(ppi_vec, input_ids_aa=input_ids_aa, input_ids_label=input_ids_label, token_type_ids=aa_type, attention_mask=attention_mask, labels=labels, position_ids=None, attention_mask_label=labels_mask, prot_vec=ppi_vec )
      lm_loss = outputs[0]
      eval_loss += lm_loss.mean().item()


    ## !! take average of last hidden layer
    hidden_GOvec = outputs[-2][12] ## batch x max_len x dim
    hidden_GOvec = hidden_GOvec[ :, max_len_in_batch::, : ] ## we remove AA, which goes from 0 to @max_len_in_batch.
    hidden_GOvec = torch.sum ( hidden_GOvec, 0 ) ## sum over batch
    if ave_GOvec is None:
      ave_GOvec = hidden_GOvec
    else:
      ave_GOvec = ave_GOvec + hidden_GOvec


    nb_eval_steps += 1
    ## track output
    norm_prob = torch.softmax( outputs[1], 1 ) ## still label x 2
    norm_prob = norm_prob.detach().cpu().numpy()[:,1] ## size is label

    if prediction is None:
      ## track predicted probability
      true_label = batch[0].data.numpy()
      prediction = np.reshape(norm_prob, ( batch[0].shape ) ) ## num actual sample v.s. num label
    else:
      true_label = np.vstack ( (true_label, batch[0].data.numpy() ) )
      prediction = np.vstack ( (prediction, np.reshape( norm_prob, ( batch[0].shape ) ) ) )


  result = evaluation_metric.all_metrics ( np.round(prediction) , true_label, yhat_raw=prediction, k=[5,10,15,20,25]) ## we can pass vector of P@k and R@k
  # evaluation_metric.print_metrics( result )
  result['eval_loss'] = eval_loss / nb_eval_steps

  output_eval_file = os.path.join(eval_output_dir, "eval_results"+prefix+".txt")
  with open(output_eval_file, "a+") as writer:
    logger.info("***** Eval results {} *****".format(prefix))
    print("\n***** Eval results {} *****".format(prefix))
    writer.write("\n***** Eval results {} *****".format(prefix))
    for key in sorted(result.keys()):
      print( "  {} = {}".format( key, str(result[key]) ) )
      # writer.write("%s = %s\n" % (key, str(result[key])))

  ## need to average out.
  ave_GOvec = ave_GOvec.detach().cpu().numpy() / len(eval_dataset)
  print ('hidden go vec dim {}'.format(ave_GOvec.shape))
  ## write out
  fout = open(args.output_dir + "/" + args.govec_outname + ".tsv","w")
  for index,name in enumerate(label_2test_array) :
    fout.write(name + '\t' + '\t'.join(str(s) for s in ave_GOvec[index]) + '\n')
  fout.close()

  return 0


def main():
  parser = argparse.ArgumentParser()

  parser.add_argument("--govec_outname", type=str, default=None)
  parser.add_argument("--save_prediction", action="store_true", default=False)
  parser.add_argument("--new_num_labels", type=int, default=None)
  parser.add_argument("--cache_name", type=str, default=None)
  parser.add_argument("--checkpoint", type=str, default=None)
  parser.add_argument("--reset_emb_zero", action="store_true", default=False)
  parser.add_argument("--aa_type_file", type=str, default=None)
  parser.add_argument("--pretrained_label_path", type=str, default=None)
  parser.add_argument("--label_2test", type=str, default=None)
  parser.add_argument("--bert_vocab", type=str, default=None)
  parser.add_argument("--config_override", action="store_true")

  ## Required parameters
  parser.add_argument("--train_data_file", default=None, type=str, required=True,
            help="The input training data file (a text file).")
  parser.add_argument("--output_dir", default=None, type=str, required=True,
            help="The output directory where the model predictions and checkpoints will be written.")

  ## Other parameters
  parser.add_argument("--eval_data_file", default=None, type=str,
            help="An optional input evaluation data file to evaluate the perplexity on (a text file).")

  parser.add_argument("--model_type", default="bert", type=str,
            help="The model architecture to be fine-tuned.")
  parser.add_argument("--model_name_or_path", default="bert-base-cased", type=str,
            help="The model checkpoint for weights initialization.")

  parser.add_argument("--mlm", action='store_true',
            help="Train with masked-language modeling loss instead of language modeling.")
  parser.add_argument("--mlm_probability", type=float, default=0.15,
            help="Ratio of tokens to mask for masked language modeling loss")

  parser.add_argument("--config_name", default="", type=str,
            help="Optional pretrained config name or path if not the same as model_name_or_path")
  parser.add_argument("--tokenizer_name", default="", type=str,
            help="Optional pretrained tokenizer name or path if not the same as model_name_or_path")
  parser.add_argument("--cache_dir", default="", type=str,
            help="Optional directory to store the pre-trained models downloaded from s3 (instread of the default one)")
  parser.add_argument("--block_size", default=-1, type=int,
            help="Optional input sequence length after tokenization."
               "The training dataset will be truncated in block of this size for training."
               "Default to the model max input length for single sentence inputs (take into account special tokens).")
  parser.add_argument("--do_train", action='store_true',
            help="Whether to run training.")
  parser.add_argument("--do_eval", action='store_true',
            help="Whether to run eval on the dev set.")
  parser.add_argument("--evaluate_during_training", action='store_true',
            help="Run evaluation during training at each logging step.")
  parser.add_argument("--do_lower_case", action='store_true',
            help="Set this flag if you are using an uncased model.")

  parser.add_argument("--per_gpu_train_batch_size", default=4, type=int,
            help="Batch size per GPU/CPU for training.")
  parser.add_argument("--per_gpu_eval_batch_size", default=4, type=int,
            help="Batch size per GPU/CPU for evaluation.")
  parser.add_argument('--gradient_accumulation_steps', type=int, default=1,
            help="Number of updates steps to accumulate before performing a backward/update pass.")
  parser.add_argument("--learning_rate", default=5e-5, type=float,
            help="The initial learning rate for Adam.")
  parser.add_argument("--weight_decay", default=0.0, type=float,
            help="Weight deay if we apply some.")
  parser.add_argument("--adam_epsilon", default=1e-8, type=float,
            help="Epsilon for Adam optimizer.")
  parser.add_argument("--max_grad_norm", default=1.0, type=float,
            help="Max gradient norm.")
  parser.add_argument("--num_train_epochs", default=1.0, type=float,
            help="Total number of training epochs to perform.")
  parser.add_argument("--max_steps", default=-1, type=int,
            help="If > 0: set total number of training steps to perform. Override num_train_epochs.")
  parser.add_argument("--warmup_steps", default=0, type=int,
            help="Linear warmup over warmup_steps.")

  parser.add_argument('--logging_steps', type=int, default=50,
            help="Log every X updates steps.")
  parser.add_argument('--save_steps', type=int, default=50,
            help="Save checkpoint every X updates steps.")
  parser.add_argument("--eval_all_checkpoints", action='store_true',
            help="Evaluate all checkpoints starting with the same prefix as model_name_or_path ending and ending with step number")
  parser.add_argument("--no_cuda", action='store_true',
            help="Avoid using CUDA when available")
  parser.add_argument('--overwrite_output_dir', action='store_true',
            help="Overwrite the content of the output directory")
  parser.add_argument('--overwrite_cache', action='store_true',
            help="Overwrite the cached training and evaluation sets")
  parser.add_argument('--seed', type=int, default=42,
            help="random seed for initialization")

  parser.add_argument('--fp16', action='store_true',
            help="Whether to use 16-bit (mixed) precision (through NVIDIA apex) instead of 32-bit")
  parser.add_argument('--fp16_opt_level', type=str, default='O1',
            help="For fp16: Apex AMP optimization level selected in ['O0', 'O1', 'O2', and 'O3']."
               "See details at https://nvidia.github.io/apex/amp.html")
  parser.add_argument("--local_rank", type=int, default=-1,
            help="For distributed training: local_rank")
  parser.add_argument('--server_ip', type=str, default='', help="For distant debugging.")
  parser.add_argument('--server_port', type=str, default='', help="For distant debugging.")
  args = parser.parse_args()

  print (args)

  if args.model_type in ["bert", "roberta"] and not args.mlm:
    raise ValueError("BERT and RoBERTa do not have LM heads but masked LM heads. They must be run using the --mlm "
             "flag (masked language modeling).")
  if args.eval_data_file is None and args.do_eval:
    raise ValueError("Cannot do evaluation without an evaluation data file. Either supply a file to --eval_data_file "
             "or remove the --do_eval argument.")

  if os.path.exists(args.output_dir) and os.listdir(args.output_dir) and args.do_train and not args.overwrite_output_dir:
    raise ValueError("Output directory ({}) already exists and is not empty. Use --overwrite_output_dir to overcome.".format(args.output_dir))

  # Setup distant debugging if needed
  if args.server_ip and args.server_port:
    # Distant debugging - see https://code.visualstudio.com/docs/python/debugging#_attach-to-a-local-script
    import ptvsd
    print("Waiting for debugger attach")
    ptvsd.enable_attach(address=(args.server_ip, args.server_port), redirect_output=True)
    ptvsd.wait_for_attach()

  # Setup CUDA, GPU & distributed training
  if args.local_rank == -1 or args.no_cuda:
    device = torch.device("cuda" if torch.cuda.is_available() and not args.no_cuda else "cpu")
    args.n_gpu = torch.cuda.device_count()
  else:  # Initializes the distributed backend which will take care of sychronizing nodes/GPUs
    torch.cuda.set_device(args.local_rank)
    device = torch.device("cuda", args.local_rank)
    torch.distributed.init_process_group(backend='nccl')
    args.n_gpu = 1
  args.device = device

  # Setup logging
  logging.basicConfig(format = '%(asctime)s - %(levelname)s - %(name)s -   %(message)s',
            datefmt = '%m/%d/%Y %H:%M:%S',
            level = logging.INFO if args.local_rank in [-1, 0] else logging.WARN)
  logger.warning("Process rank: %s, device: %s, n_gpu: %s, distributed training: %s, 16-bits training: %s",
          args.local_rank, device, args.n_gpu, bool(args.local_rank != -1), args.fp16)

  # Set seed
  set_seed(args)

  # read in labels to be testing
  label_2test_array = pd.read_csv(args.label_2test,header=None)
  label_2test_array = sorted(list( label_2test_array[0] ))
  label_2test_array = [re.sub(":","",lab) for lab in label_2test_array] ## splitting has problem with the ":"
  num_labels = len(label_2test_array)

  # Load pretrained model and tokenizer
  if args.local_rank not in [-1, 0]:
    torch.distributed.barrier()  # Barrier to make sure only the first process in distributed training download model & vocab

  config_class, model_class, tokenizer_class = MODEL_CLASSES[args.model_type]

  if args.bert_vocab is None:
    tokenizer = tokenizer_class.from_pretrained(args.tokenizer_name if args.tokenizer_name else args.model_name_or_path, do_lower_case=args.do_lower_case)
  else:
    tokenizer = BertTokenizer.from_pretrained(args.bert_vocab, do_lower_case=args.do_lower_case)

  if args.block_size <= 0:
    args.block_size = tokenizer.max_len_single_sentence  # Our input block size will be the max possible for the model
  args.block_size = min(args.block_size, tokenizer.max_len_single_sentence)

  config = BertConfig.from_pretrained(args.config_name) ## should we always override

  if args.new_num_labels is None: ## OTHERWISE, we are now expanding, so we will use @resize_token_embeddings
    config.label_size = len(label_2test_array) ## make sure we really get correct label

  if (config.pretrained_vec) and (args.pretrained_label_path is None):
    print ('\n\ncheck that pretrained label vecs are properly turned on/off.')
    exit()

  if args.aa_type_file is not None: ## read protein sequence extra data
    print ('load in aa_type_file {}'.format(args.aa_type_file))
    annot_data = pickle.load ( open ( args.aa_type_file, 'rb' ) )
    print ('len of aa_type_file without special token {}'.format(len(annot_data)))
    config.type_vocab_size = len(annot_data) + 2 # notice add 2 because PAD and UNK

  config.output_attentions = True
  config.output_hidden_states = True

  # Prepare model
  print ('\nsee config before init model')
  print (config)

  if args.config_override and (args.new_num_labels is None) :
    model = model_class(config)
  else:
    model = model_class.from_pretrained(args.model_name_or_path, from_tf=bool('.ckpt' in args.model_name_or_path), config=config)

  # print ('\ninit weight (scale/shift)')
  # model.init_weights() ## init weight (scale/shift)

  ## fix emb into 0
  if args.reset_emb_zero:
    print ('\nreset token-type emb at position 0 into 0\n')
    model.bert.embeddings.token_type_embeddings.weight.data[0] = 0 ## only set 1st one to zero, which is padding

  ## load pretrain label vectors ?
  if args.pretrained_label_path is not None:
    if args.new_num_labels is not None: # run on more labels
      model.bert.resize_label_embeddings(args.new_num_labels)
      num_labels = args.new_num_labels
      print ('\nresize label emb to have more labels than trained model')
      print (model.bert.embeddings_label.word_embeddings)

    print ('\nload pretrained label vec {}\n'.format(args.pretrained_label_path))
    pretrained_label_vec = np.zeros((num_labels,256))
    temp = pickle.load(open(args.pretrained_label_path,"rb")) ## have a pickle right now... but it should be .txt for easier use
    for counter, lab in enumerate( label_2test_array ):
      pretrained_label_vec[counter] = temp[re.sub("GO","GO:",lab)]
    #
    model.init_label_emb(pretrained_label_vec)

  print ('\nsee model\n')
  print (model)

  model.to(args.device)

  if args.local_rank == 0:
    torch.distributed.barrier()  # End of barrier to make sure only the first process in distributed training download model & vocab

  logger.info("Training/evaluation parameters %s", args)


  # Training
  if args.do_train:
    if args.local_rank not in [-1, 0]:
      torch.distributed.barrier()  # Barrier to make sure only the first process in distributed training process the dataset, and the others will use the cache

    train_dataset = load_and_cache_examples(args, tokenizer, label_2test_array, evaluate=False, config=config)

    if args.local_rank == 0:
      torch.distributed.barrier()

    global_step, tr_loss = train(args, train_dataset, model, tokenizer, label_2test_array, config=config)
    logger.info(" global_step = %s, average loss = %s", global_step, tr_loss)


  # Saving best-practices: if you use save_pretrained for the model and tokenizer, you can reload them using from_pretrained()
  if args.do_train and (args.local_rank == -1 or torch.distributed.get_rank() == 0):
    # Create output directory if needed
    if not os.path.exists(args.output_dir) and args.local_rank in [-1, 0]:
      os.makedirs(args.output_dir)

    logger.info("Saving model checkpoint to %s", args.output_dir)
    # Save a trained model, configuration and tokenizer using `save_pretrained()`.
    # They can then be reloaded using `from_pretrained()`
    model_to_save = model.module if hasattr(model, 'module') else model  # Take care of distributed/parallel training
    model_to_save.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    # Good practice: save your training arguments together with the trained model
    torch.save(args, os.path.join(args.output_dir, 'training_args.bin'))

    # Load a trained model and vocabulary that you have fine-tuned
    model = model_class.from_pretrained(args.output_dir)
    tokenizer = tokenizer_class.from_pretrained(args.output_dir, do_lower_case=args.do_lower_case)
    model.to(args.device)

  if args.new_num_labels is not None:
    result = evaluate(args, model, tokenizer, label_2test_array, prefix='zeroshot', config=config)
    return result

  # Evaluation
  results = {}
  if args.do_eval and args.local_rank in [-1, 0]:
    checkpoints = [args.output_dir]
    if args.eval_all_checkpoints:
      checkpoints = list(os.path.dirname(c) for c in sorted(glob.glob(args.output_dir + '/**/' + WEIGHTS_NAME, recursive=True)))
      logging.getLogger("pytorch_transformers.modeling_utils").setLevel(logging.WARN)  # Reduce logging
    logger.info("Evaluate the following checkpoints: %s", checkpoints)

    if args.checkpoint is not None: ## we don't have to do all checkpoints ??
      checkpoints = [c for c in checkpoints if re.findall(args.checkpoint,c)]
      print ('\nwill only do this one checkpoint {}'.format(checkpoints))

    for checkpoint in checkpoints:
      print( "\n\nEvaluate the following checkpoints: {} \n".format(checkpoint) )
      global_step = checkpoint.split('-')[-1] if len(checkpoints) > 1 else ""
      model = model_class.from_pretrained(checkpoint)
      model.to(args.device)
      result = evaluate(args, model, tokenizer, label_2test_array, prefix=global_step, config=config)
      result = dict((k + '_{}'.format(global_step), v) for k, v in result.items())
      results.update(result)

  return results


if __name__ == "__main__":
  main()
