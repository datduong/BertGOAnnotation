import sys,re,os,pickle
import numpy as np
import pandas as pd

sys.path.append("/u/scratch/d/datduong/GOAnnotationTransformer")
import TransformerModel.TokenClassifier as TokenClassifier

sys.path.append("/u/scratch/d/datduong/GOAnnotationTransformer/TrainModel")
import evaluation_metric
import PosthocCorrect


def eval (prediction_dict,sub_array=None,path="",add_name="", filter_down=False):
  prediction = prediction_dict['prediction']
  true_label = prediction_dict['true_label']
  if sub_array is not None:
    print ('len label {}'.format(len(sub_array)))
    prediction = prediction [ : , sub_array ] ## obs x label
    true_label = true_label [ : , sub_array ]
  #
  # threshold_fmax=np.arange(0.0001,1,.005)
  if filter_down == True: ##!! when eval rare terms, what if only a few proteins have them??
    print ('dim before remove {}'.format(prediction.shape))
    where = np.where( np.sum(true_label,axis=1) > 0 )[0]
    print ('retain these prot {}'.format(len(where)))
    prediction = prediction[where]
    print ('check dim {}'.format(prediction.shape))
    true_label = true_label[where]
  #
  result = evaluation_metric.all_metrics ( np.round(prediction) , true_label, yhat_raw=prediction, k=[5,15,10,20,30,40,50,60,70,80,90,100],path=path,add_name=add_name)
  return result

def get_label_by_count (count_file) :
  count_file = pd.read_csv(count_file,sep="\t") # GO  count
  quantile = np.quantile( list (count_file['count']) , q=[0.25,.75] )
  low = count_file[count_file['count'] <= quantile[0]]
  low = sorted ( list(low['GO']) )
  high = count_file[count_file['count'] >= quantile[1]]
  high = sorted ( list(high['GO']) )
  middle = count_file[ (count_file['count'] > quantile[0]) & (count_file['count'] < quantile[1]) ]
  middle = sorted ( list(middle['GO']) )
  return low, middle, high


def submitJobs (where,count_file,method,save_file_type,filter_down):

  os.chdir(where)

  if filter_down == 'none':
    filter_down = False
  else:
    filter_down = True

  for onto in ['cc','mf','bp']:

    print ('\n\ntype {}'.format(onto))

    label_original = pd.read_csv('/u/scratch/d/datduong/deepgo/data/train/deepgo.'+onto+'.csv',sep="\t",header=None)
    label_original = sorted(list(label_original[0])) ## we sort labels in training

    #### compute accuracy by frequency

    low, middle, high = get_label_by_count (count_file+'/CountGoInTrain-'+onto+'.tsv')
    low_index = np.array ( [ index for index, value in enumerate(label_original) if value in low ] )
    middle_index = np.array ( [ index for index, value in enumerate(label_original) if value in middle ] )
    high_index = np.array ( [ index for index, value in enumerate(label_original) if value in high ] )

    prediction_dict = pickle.load(open("/u/scratch/d/datduong/deepgo/data/BertNotFtAARawSeqGO/"+onto+"/"+method+"/"+save_file_type+".pickle","rb"))

    path="/u/scratch/d/datduong/deepgo/data/BertNotFtAARawSeqGO/"+onto+"/"+method

    print ('\nsize {}\n'.format(prediction_dict['prediction'].shape))

    print ('\nwhole {}'.format(onto))
    evaluation_metric.print_metrics( eval(prediction_dict, path=path, add_name='whole'))

    print('\nlow {}'.format(onto))
    evaluation_metric.print_metrics( eval(prediction_dict, low_index, path=path, add_name='low', filter_down=filter_down) )

    print ('\nmiddle {}'.format(onto))
    evaluation_metric.print_metrics( eval(prediction_dict, middle_index, path=path, add_name='middle') )

    print ('\nhigh {}'.format(onto))
    evaluation_metric.print_metrics( eval(prediction_dict, high_index, path=path, add_name='high') )



if len(sys.argv)<1: #### run script
	print("Usage: \n")
	sys.exit(1)
else:
	submitJobs ( sys.argv[1] , sys.argv[2] , sys.argv[3] , sys.argv[4] , sys.argv[5] )



