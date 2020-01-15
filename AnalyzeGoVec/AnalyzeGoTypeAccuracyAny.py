import sys,re,os,pickle
import numpy as np
import pandas as pd

sys.path.append("/u/scratch/d/datduong/BertGOAnnotation")
import KmerModel.TokenClassifier as TokenClassifier

sys.path.append("/u/scratch/d/datduong/BertGOAnnotation/finetune")
import evaluation_metric


def eval (prediction_dict,sub_array=None,path="",add_name=""):
  prediction = prediction_dict['prediction']
  try:
    true_label = prediction_dict['true_label']
  except: 
    true_label = prediction_dict['truth']
  if sub_array is not None:
    prediction = prediction [ : , sub_array ] ## obs x label
    true_label = true_label [ : , sub_array ]
  #
  # threshold_fmax=np.arange(0.0001,1,.005)
  result = evaluation_metric.all_metrics ( np.round(prediction) , true_label, yhat_raw=prediction, k=[10,20,30,40,50],path=path,add_name=add_name)
  return result 

#### check accuracy of labels not seen in training.
#### pure zeroshot approach.

def submitJobs (onto,prediction_dict,save_file_type,path):

  print ('\n\ntype {}'.format(onto))

  label_original = pd.read_csv('/u/scratch/d/datduong/deepgo/data/train/deepgo.'+onto+'.csv',sep="\t",header=None)
  label_original = set(list(label_original[0]))

  label_large = pd.read_csv('/u/scratch/d/datduong/deepgo/dataExpandGoSet/train/deepgo.'+onto+'.csv',sep="\t",header=None)
  label_large = set(list(label_large[0]))

  label_unseen = sorted ( list ( label_large - label_original ) )
  label_large = sorted(list(label_large)) ## by default we sort label for the model
  label_original = sorted(list(label_original))

  label_lookup = {value:counter for counter,value in enumerate(label_large)}
  label_unseen_pos = np.array ( [label_lookup[v] for v in label_lookup if v in label_unseen ] )
  label_seen_pos = np.array ( [label_lookup[v] for v in label_lookup if v in label_original ] )

  #### want to compute accuracy on original set of labels, then on unseen labels
  #### possible original set prediction will change because we do joint prediction. so attention weight will affect outcome

  ##!! prediction_train_all_on_test.pickle save_prediction_expand
  try:
    prediction_dict = pickle.load(open(prediction_dict,"rb"))
  except:
    print ('\npass {}'.format(onto))
    exit()

  print ('\nsize {}\n'.format(prediction_dict['prediction'].shape))

  if save_file_type == 'prediction_train_all_on_test':
    print ('\nwhole {}'.format(onto))
    evaluation_metric.print_metrics( eval(prediction_dict, path=path, add_name='whole'))

  if save_file_type == 'save_prediction_expand':

    print('\noriginal {}'.format(onto))
    evaluation_metric.print_metrics( eval(prediction_dict, label_seen_pos, path=path, add_name='original') )

    print ('\nunseen {}'.format(onto))
    evaluation_metric.print_metrics( eval(prediction_dict, label_unseen_pos, path=path, add_name='unseen') )



if len(sys.argv)<1: #### run script
	print("Usage: \n")
	sys.exit(1)
else:
	submitJobs ( sys.argv[1] , sys.argv[2] , sys.argv[3] , sys.argv[4] )


