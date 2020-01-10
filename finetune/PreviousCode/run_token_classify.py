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


MODEL_CLASSES = {
  'gpt2': (GPT2Config, GPT2LMHeadModel, GPT2Tokenizer),
  'openai-gpt': (OpenAIGPTConfig, OpenAIGPTLMHeadModel, OpenAIGPTTokenizer),
  'bert': (BertConfig, TokenClassifier.BertForTokenClassification1hot, BertTokenizer), ## replace the standard @BertForTokenClassification
  'roberta': (RobertaConfig, RobertaForMaskedLM, RobertaTokenizer)
}


class TextDataset(Dataset):
  def __init__(self, tokenizer, label_2test_array, file_path='train', block_size=512):
    assert os.path.isfile(file_path)
    directory, filename = os.path.split(file_path)
    cached_features_file = os.path.join(directory, f'cached_lm_{block_size}_{filename}')

    label_2test_array = sorted(label_2test_array) ## just to be sure we keep alphabet
    num_label = len(label_2test_array)
    print ('num label {}'.format(num_label))
    ## faster look up
    label_index_map = { name : index for index,name in enumerate(label_2test_array) }
    label_string = " ".join(label_2test_array)

    if os.path.exists(cached_features_file+'examples'): ## take 1 thing to test if it exists
      logger.info("Loading features from cached file %s", cached_features_file)
      with open(cached_features_file+'examples', 'rb') as handle:
        self.examples = pickle.load(handle)
      with open(cached_features_file+'attention_mask', 'rb') as handle:
        self.attention_mask = pickle.load(handle)
      with open(cached_features_file+'label1hot', 'rb') as handle:
        self.label1hot = pickle.load(handle)
      with open(cached_features_file+'label_mask', 'rb') as handle:
        self.label_mask = pickle.load(handle)
      with open(cached_features_file+'token_type', 'rb') as handle:
        self.token_type = pickle.load(handle)

    else:
      logger.info("Creating features from dataset file at %s", directory)

      self.attention_mask = []
      self.examples = []
      self.label1hot = [] ## take 1 hot (should short labels by alphabet)
      self.label_mask = []
      self.token_type = []

      fin = open(file_path,"r",encoding='utf-8')
      for counter, text in tqdm(enumerate(fin)):
        # if counter > 100 :
        #   break
        text = text.strip()
        if len(text) == 0: ## skip blank ??
          continue

        ## split at \t ?? [seq \t label]
        text = text.split("\t") ## position 0 is kmer sequence, position 1 is list of labels
        kmer_text = text[0].split() ## !! we must not use string text, otherwise, we will get wrong len
        num_kmer_text = len(kmer_text)
        this_label = text[1].split() ## by space

        ## convert label into 1-hot style
        label1hot = np.zeros(num_label) ## 1D array
        index_as1 = [label_index_map[label] for label in this_label]
        label1hot [ index_as1 ] = 1
        self.label1hot.append( label1hot )

        ## create token_type
        token_type = [0]*(num_kmer_text+2) + [1]*(num_label+1) ## add 2 because of cls and sep, ## add 1 because of sep
        WHERE_KMER_END = num_kmer_text + 2 ## add 2 because of sep cls , so we can mask out Kmer, because we will only predict the labels

        ## combine the labels back with the kmer text ??
        ## want kmer + ALL LABELS
        ## ok to use @text[0] because we will tokenize, so we will remove the space
        text = text[0] + " [SEP] " + label_string ## add all the labels
        text_split = tokenizer.tokenize(text)
        tokenized_text = tokenizer.convert_tokens_to_ids(text_split) ## the tab won't matter here ## split at \t ?? [seq \t label]

        if len(tokenized_text) < block_size : ## short enough, so just use it
          ## add padding to match block_size
          tokens = tokenizer.add_special_tokens_single_sentence(tokenized_text) ## [CLS] something [SEP]
          attention_indicator = [1]*len(tokens) + [0]*(block_size-len(tokens))
          tokens = tokens + [0]*(block_size-len(tokens)) ## add padding 0

          assert len(tokens) == block_size
          assert len(attention_indicator) == block_size

          self.examples.append(tokens)
          self.attention_mask.append(attention_indicator)

          token_type = token_type + [0]* (block_size-len(token_type)) ## zero here, because we use mask anyway, so doesn't matter ... add 0-padding to the token types
          self.token_type.append(token_type)

          ## get label_mask, so we test only on labels we want, and not some random tokens
          label_mask = np.zeros( block_size ) ## 0--> not attend to
          label_mask [ WHERE_KMER_END:(WHERE_KMER_END+num_label) ] = 1 ## set to 1 so we can pull these out later, ALL LABELS WILL NEED 1, NOT JUST THE TRUE LABEL
          self.label_mask.append(label_mask)

          if counter < 3:
            print ('\nsee input text\n {}'.format(tokens))

        else:
          print ( 'too long, code unable to split long sentence ... infact we should not split ... block {} len {}'.format(block_size,len(tokenized_text)) )
          exit()
          # while len(tokenized_text) >= block_size:  # Truncate in block of block_size
          #   self.examples.append(tokenizer.add_special_tokens_single_sentence(tokenized_text[:block_size]))
          #   tokenized_text = tokenized_text[block_size:]
          #   attention_indicator = [1]*block_size
          #   self.attention_mask.append(attention_indicator)

      ## save at end
      logger.info("To save read/write time... Saving features into cached file %s", cached_features_file)
      with open(cached_features_file+'examples', 'wb') as handle:
        pickle.dump(self.examples, handle, protocol=pickle.HIGHEST_PROTOCOL)
      with open(cached_features_file+'attention_mask', 'wb') as handle:
        pickle.dump(self.attention_mask, handle, protocol=pickle.HIGHEST_PROTOCOL)
      with open(cached_features_file+'label1hot', 'wb') as handle:
        pickle.dump(self.label1hot, handle, protocol=pickle.HIGHEST_PROTOCOL)
      with open(cached_features_file+'label_mask', 'wb') as handle:
        pickle.dump(self.label_mask, handle, protocol=pickle.HIGHEST_PROTOCOL)
      with open(cached_features_file+'token_type', 'wb') as handle:
        pickle.dump(self.token_type, handle, protocol=pickle.HIGHEST_PROTOCOL)

  def __len__(self):
    return len(self.examples)

  def __getitem__(self, item):
    return (torch.tensor(self.attention_mask[item]), torch.tensor(self.examples[item]),
            torch.LongTensor(self.label1hot[item]), torch.tensor(self.label_mask[item]),
            torch.tensor(self.token_type[item]) )


def load_and_cache_examples(args, tokenizer, label_2test_array, evaluate=False):
  dataset = TextDataset(tokenizer, label_2test_array, file_path=args.eval_data_file if evaluate else args.train_data_file, block_size=args.block_size)
  return dataset


def set_seed(args):
  random.seed(args.seed)
  np.random.seed(args.seed)
  torch.manual_seed(args.seed)
  if args.n_gpu > 0:
    torch.cuda.manual_seed_all(args.seed)


def train(args, train_dataset, model, tokenizer, label_2test_array):
  """ Train the model """

  num_labels = len(label_2test_array)
  print ("\nnum_labels {}\n".format(num_labels))

  if args.local_rank in [-1, 0]:
    tb_writer = SummaryWriter()

  args.train_batch_size = args.per_gpu_train_batch_size * max(1, args.n_gpu)
  train_sampler = RandomSampler(train_dataset) if args.local_rank == -1 else DistributedSampler(train_dataset)
  train_dataloader = DataLoader(train_dataset, sampler=train_sampler, batch_size=args.train_batch_size)

  if args.max_steps > 0:
    t_total = args.max_steps
    args.num_train_epochs = args.max_steps // (len(train_dataloader) // args.gradient_accumulation_steps) + 1
  else:
    t_total = len(train_dataloader) // args.gradient_accumulation_steps * args.num_train_epochs

  # Prepare optimizer and schedule (linear warmup and decay)
  no_decay = ['bias', 'LayerNorm.weight']
  optimizer_grouped_parameters = [
    {'params': [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)], 'weight_decay': args.weight_decay},
    {'params': [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)], 'weight_decay': 0.0}
    ]
  optimizer = AdamW(optimizer_grouped_parameters, lr=args.learning_rate, eps=args.adam_epsilon)
  scheduler = WarmupLinearSchedule(optimizer, warmup_steps=args.warmup_steps, t_total=t_total)
  if args.fp16:
    try:
      from apex import amp
    except ImportError:
      raise ImportError("Please install apex from https://www.github.com/nvidia/apex to use fp16 training.")
    model, optimizer = amp.initialize(model, optimizer, opt_level=args.fp16_opt_level)

  # multi-gpu training (should be after apex fp16 initialization)
  if args.n_gpu > 1:
    model = torch.nn.DataParallel(model)

  # Distributed training (should be after apex fp16 initialization)
  if args.local_rank != -1:
    model = torch.nn.parallel.DistributedDataParallel(model, device_ids=[args.local_rank],
                              output_device=args.local_rank,
                              find_unused_parameters=True)

  # Train!
  logger.info("***** Running training *****")
  logger.info("  Num examples = %d", len(train_dataset))
  logger.info("  Num Epochs = %d", args.num_train_epochs)
  logger.info("  Instantaneous batch size per GPU = %d", args.per_gpu_train_batch_size)
  logger.info("  Total train batch size (w. parallel, distributed & accumulation) = %d",
           args.train_batch_size * args.gradient_accumulation_steps * (torch.distributed.get_world_size() if args.local_rank != -1 else 1))
  logger.info("  Gradient Accumulation steps = %d", args.gradient_accumulation_steps)
  logger.info("  Total optimization steps = %d", t_total)

  global_step = 0
  tr_loss, logging_loss = 0.0, 0.0
  model.zero_grad()
  train_iterator = trange(int(args.num_train_epochs), desc="Epoch", disable=args.local_rank not in [-1, 0])

  ## track best loss on eval set ??
  eval_loss = np.inf
  last_best = 0
  break_early = False

  set_seed(args)  # Added here for reproducibility (even between python 2 and 3)

  for epoch_counter in train_iterator:
    epoch_iterator = tqdm(train_dataloader, desc="Iteration", disable=args.local_rank not in [-1, 0])
    for step, batch in enumerate(epoch_iterator):
      # inputs, labels, attention_mask = mask_tokens(batch, tokenizer, args) if args.mlm else (batch, batch)
      ## !!!  WE ARE NOT GOING TO TRAIN MASKED-LM

      ## also, the batch will have this ordering
      # return (torch.tensor(self.attention_mask[item]), torch.tensor(self.examples[item]),
      #       torch.LongTensor(self.label1hot[item]), torch.LongTensor(self.label_mask[item]),
      #       torch.tensor(self.token_type[item]) )

      max_len_in_batch = int( torch.max ( torch.sum(batch[0],1) ) ) ## only need max len
      attention_mask = batch[0][:,0:max_len_in_batch].to(args.device)
      inputs = batch[1][:,0:max_len_in_batch].to(args.device)
      labels = batch[2].to(args.device) ## already in batch_size x num_label
      labels_mask = batch[3][:,0:max_len_in_batch].to(args.device) ## extract out labels from the array input... probably doesn't need this to be in GPU
      token_type = batch[4][:,0:max_len_in_batch].to(args.device)

      model.train()

      # call to the @model
      # def forward(self, input_ids, token_type_ids=None, attention_mask=None, labels=None,
      #   position_ids=None, head_mask=None, attention_mask_label=None):

      outputs = model(inputs, token_type_ids=token_type, attention_mask=attention_mask, labels=labels, position_ids=None, attention_mask_label=labels_mask )  # if args.mlm else model(inputs, labels=labels)

      loss = outputs[0]  # model outputs are always tuple in pytorch-transformers (see doc)

      if args.n_gpu > 1:
        loss = loss.mean()  # mean() to average on multi-gpu parallel training
      if args.gradient_accumulation_steps > 1:
        loss = loss / args.gradient_accumulation_steps

      if args.fp16:
        with amp.scale_loss(loss, optimizer) as scaled_loss:
          scaled_loss.backward()
      else:
        loss.backward()

      tr_loss += loss.item()
      if (step + 1) % args.gradient_accumulation_steps == 0:
        if args.fp16:
          torch.nn.utils.clip_grad_norm_(amp.master_params(optimizer), args.max_grad_norm)
        else:
          torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
        optimizer.step()
        scheduler.step()  # Update learning rate schedule
        model.zero_grad()
        global_step += 1

        if (epoch_counter>0) and args.local_rank in [-1, 0] and args.save_steps > 0 and global_step % args.save_steps == 0:
          # Save model checkpoint
          output_dir = os.path.join(args.output_dir, 'checkpoint-{}'.format(global_step))
          if not os.path.exists(output_dir):
            os.makedirs(output_dir)
          model_to_save = model.module if hasattr(model, 'module') else model  # Take care of distributed/parallel training
          model_to_save.save_pretrained(output_dir)
          torch.save(args, os.path.join(output_dir, 'training_args.bin'))
          logger.info("Saving model checkpoint to %s", output_dir)

        if args.local_rank in [-1, 0] and args.logging_steps > 0 and global_step % args.logging_steps == 0:
          # Log metrics
          if args.local_rank == -1 and args.evaluate_during_training:  # Only evaluate when single GPU otherwise metrics may not average well
            results = evaluate(args, model, tokenizer,label_2test_array)
            for key, value in results.items():
              tb_writer.add_scalar('eval_{}'.format(key), value, global_step)

          tb_writer.add_scalar('lr', scheduler.get_lr()[0], global_step)
          tb_writer.add_scalar('loss', (tr_loss - logging_loss)/args.logging_steps, global_step)
          logging_loss = tr_loss

      if args.max_steps > 0 and global_step > args.max_steps:
        epoch_iterator.close()
        break


    ## end 1 epoch
    results = evaluate(args, model, tokenizer,label_2test_array)
    if results['eval_loss'] < eval_loss:
      eval_loss = results['eval_loss']
      last_best = epoch_counter
      break_early = False
      print ('\nupdate lowest loss on epoch {}, {}\nreset break_early to False, see break_early variable {}'.format(epoch_counter,eval_loss,break_early))
    else:
      if epoch_counter - last_best > 5 : ## break counter after 5 epoch
        # break ## break early
        break_early = True
        print ('epoch {} set break_early to True, see break_early variable {}'.format(epoch_counter,break_early))

    if break_early:
      train_iterator.close()
      print ("**** break early ****")
      break

    # print ('\neval on trainset\n')
    # true_label = np.array (true_label)
    # result = evaluation_metric.all_metrics ( np.round(prediction) , true_label, yhat_raw=prediction, k=[5,10,15,20,25]) ## we can pass vector of P@k and R@k
    # evaluation_metric.print_metrics( result )

    if args.max_steps > 0 and global_step > args.max_steps:
      train_iterator.close()
      break

  if args.local_rank in [-1, 0]:
    tb_writer.close()

  return global_step, tr_loss / global_step


def evaluate(args, model, tokenizer, label_2test_array, prefix=""):

  num_labels = len(label_2test_array)

  # Loop to handle MNLI double evaluation (matched, mis-matched)
  eval_output_dir = args.output_dir

  eval_dataset = load_and_cache_examples(args, tokenizer, label_2test_array, evaluate=True)

  if not os.path.exists(eval_output_dir) and args.local_rank in [-1, 0]:
    os.makedirs(eval_output_dir)

  args.eval_batch_size = args.per_gpu_eval_batch_size * max(1, args.n_gpu)
  # Note that DistributedSampler samples randomly
  eval_sampler = SequentialSampler(eval_dataset) if args.local_rank == -1 else DistributedSampler(eval_dataset)
  eval_dataloader = DataLoader(eval_dataset, sampler=eval_sampler, batch_size=args.eval_batch_size)

  # Eval!
  logger.info("***** Running evaluation {} *****".format(prefix))
  logger.info("  Num examples = %d", len(eval_dataset))
  logger.info("  Batch size = %d", args.eval_batch_size)
  eval_loss = 0.0
  nb_eval_steps = 0
  model.eval()

  prediction = None
  true_label = None

  for batch in tqdm(eval_dataloader, desc="Evaluating"):
    # batch = batch.to(args.device)

    max_len_in_batch = int( torch.max ( torch.sum(batch[0],1) ) ) ## only need max len
    attention_mask = batch[0][:,0:max_len_in_batch].to(args.device)
    inputs = batch[1][:,0:max_len_in_batch].to(args.device)
    labels = batch[2].to(args.device) ## already in batch_size x num_label
    labels_mask = batch[3][:,0:max_len_in_batch].to(args.device) ## extract out labels from the array input... probably doesn't need this to be in GPU
    token_type = batch[4][:,0:max_len_in_batch].to(args.device)

    with torch.no_grad():
      outputs = model(inputs, token_type_ids=token_type, attention_mask=attention_mask, labels=labels, position_ids=None, attention_mask_label=labels_mask )
      lm_loss = outputs[0]
      eval_loss += lm_loss.mean().item()
    nb_eval_steps += 1

    ## track output
    norm_prob = torch.softmax( outputs[1], 1 ) ## still label x 2
    norm_prob = norm_prob.detach().cpu().numpy()[:,1] ## size is label
    # print (norm_prob.shape)
    if prediction is None:
      ## track predicted probability
      true_label = batch[2].data.numpy()
      prediction = np.reshape(norm_prob, ( batch[1].shape[0], num_labels ) )## num actual sample v.s. num label
    else:
      true_label = np.vstack ( (true_label, batch[2].data.numpy() ) )
      prediction = np.vstack ( (prediction, np.reshape( norm_prob, ( batch[1].shape[0], num_labels )  ) )  )


  true_label = np.array (true_label)
  result = evaluation_metric.all_metrics ( np.round(prediction) , true_label, yhat_raw=prediction, k=[5,10,15,20,25]) ## we can pass vector of P@k and R@k
  # evaluation_metric.print_metrics( result )

  result['eval_loss'] = eval_loss / nb_eval_steps

  output_eval_file = os.path.join(eval_output_dir, "eval_results.txt")
  with open(output_eval_file, "a+") as writer:
    logger.info("***** Eval results {} *****".format(prefix))
    print("\n***** Eval results {} *****".format(prefix))
    writer.write("\n***** Eval results {} *****".format(prefix))
    for key in sorted(result.keys()):
      print( "  {} = {}".format( key, str(result[key]) ) ) 
      # writer.write("%s = %s\n" % (key, str(result[key])))


  return result


def main():
  parser = argparse.ArgumentParser()

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

  # Load pretrained model and tokenizer
  if args.local_rank not in [-1, 0]:
    torch.distributed.barrier()  # Barrier to make sure only the first process in distributed training download model & vocab

  config_class, model_class, tokenizer_class = MODEL_CLASSES[args.model_type]
  config = config_class.from_pretrained(args.config_name if args.config_name else args.model_name_or_path)

  if args.bert_vocab is None:
    tokenizer = tokenizer_class.from_pretrained(args.tokenizer_name if args.tokenizer_name else args.model_name_or_path, do_lower_case=args.do_lower_case)
  else:
    tokenizer = BertTokenizer.from_pretrained(args.bert_vocab, do_lower_case=args.do_lower_case)

  if args.block_size <= 0:
    args.block_size = tokenizer.max_len_single_sentence  # Our input block size will be the max possible for the model
  args.block_size = min(args.block_size, tokenizer.max_len_single_sentence)


  # Prepare model
  if args.config_override:
    # config = BertConfig.from_pretrained(args.config_name)
    model = model_class(config)
  else:
    model = model_class.from_pretrained(args.model_name_or_path, from_tf=bool('.ckpt' in args.model_name_or_path), config=config)

  model.to(args.device)

  if args.local_rank == 0:
    torch.distributed.barrier()  # End of barrier to make sure only the first process in distributed training download model & vocab

  logger.info("Training/evaluation parameters %s", args)

  # read in labels to be testing
  label_2test_array = pd.read_csv(args.label_2test,header=None)
  label_2test_array = sorted(list( label_2test_array[0] ))
  label_2test_array = [re.sub(":","",lab) for lab in label_2test_array] ## splitting has problem with the ":"

  # Training
  if args.do_train:
    if args.local_rank not in [-1, 0]:
      torch.distributed.barrier()  # Barrier to make sure only the first process in distributed training process the dataset, and the others will use the cache

    train_dataset = load_and_cache_examples(args, tokenizer, label_2test_array, evaluate=False)

    if args.local_rank == 0:
      torch.distributed.barrier()

    global_step, tr_loss = train(args, train_dataset, model, tokenizer,label_2test_array)
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


  # Evaluation
  results = {}
  if args.do_eval and args.local_rank in [-1, 0]:
    checkpoints = [args.output_dir]
    if args.eval_all_checkpoints:
      checkpoints = list(os.path.dirname(c) for c in sorted(glob.glob(args.output_dir + '/**/' + WEIGHTS_NAME, recursive=True)))
      logging.getLogger("pytorch_transformers.modeling_utils").setLevel(logging.WARN)  # Reduce logging
    logger.info("Evaluate the following checkpoints: %s", checkpoints)
    for checkpoint in checkpoints:
      print( "\n\nEvaluate the following checkpoints: {} \n".format(checkpoint) )
      global_step = checkpoint.split('-')[-1] if len(checkpoints) > 1 else ""
      model = model_class.from_pretrained(checkpoint)
      model.to(args.device)
      result = evaluate(args, model, tokenizer, label_2test_array, prefix=global_step)
      result = dict((k + '_{}'.format(global_step), v) for k, v in result.items())
      results.update(result)

  return results


if __name__ == "__main__":
  main()
