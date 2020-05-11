

import re,os,sys,pickle
import numpy as np
import pandas as pd

sys.path.append("/u/scratch/d/datduong/GOAnnotationTransformer/TrainModel")
import evaluation_metric

def GetCountDict (filename):
  count = {}
  name = []
  fin = open (filename,'r')
  for line in fin:
    line = line.strip().split()
    line[0] = re.sub("GO:","GO",line[0]) ## keep GOxyz
    count[line[0]] = int (line[1])
    name.append(line[0])
  fin.close()
  return count, name

def GetNumObsPerQuantile (count_dict,q=[.25,.75]):
  count = [count_dict[k] for k in count_dict]
  quant = np.quantile(count,q)
  print ( '\nquantiles {}\n'.format(quant) )
  return quant

def GetIndexOfLabelInQuantRange (label_to_test,count_dict):
  quantile_range = GetNumObsPerQuantile(count_dict) # ! 25 and 75 for now.
  quantile_index = {'25':[], '25-75':[], '75':[] }
  for index, label in enumerate (label_to_test): # ! keep same ordering as in input file. this file should already be sorted.
    if count_dict[label] < quantile_range[0] : # less 25%
      quantile_index['25'].append(index)
    elif count_dict[label] > quantile_range[1] : # over 75%
      quantile_index['75'].append(index)
    else:
      quantile_index['25-75'].append(index)
  #
  for key,value in quantile_index.items(): 
    quantile_index[key] = np.array (value) ## convert to np for indexing
  return quantile_index

def eval (prediction_dict,sub_array=None): ## ! eval accuracy of labels ...
  prediction = prediction_dict['prediction']
  key_name = 'truth'
  if key_name not in prediction_dict: # ! different save pickle has different names
    key_name = 'true_label'
  #
  true_label = prediction_dict[key_name] # true_label, truth
  if sub_array is not None:
    prediction = prediction [ : , sub_array ] ## obs x label
    true_label = true_label [ : , sub_array ]
  #
  result = evaluation_metric.all_metrics ( np.round(prediction) , true_label, yhat_raw=prediction, k=np.arange(10,110,10).tolist() )
  return result

def submitJobs (label_path, onto, load_path):

  # for onto in ['cc','mf','bp']:

  label_count , label_name = GetCountDict(label_path)

  quantile_index = GetIndexOfLabelInQuantRange(label_name,label_count)

  prediction_dict = pickle.load(open(load_path,"rb"))

  print ('\nmodel {} type {}'.format(load_path, onto ))
  print ('\nsize {}\n'.format(prediction_dict['prediction'].shape))

  print ('\nwhole')
  evaluation_metric.print_metrics( eval(prediction_dict) )

  for quant in ['25','25-75','75']:
    print('\nq {}'.format(quant))
    evaluation_metric.print_metrics( eval(prediction_dict, quantile_index[quant]) )


if len(sys.argv)<1: #### run script
	print("Usage: \n")
	sys.exit(1)
else:
	submitJobs ( sys.argv[1], sys.argv[2], sys.argv[3] )

