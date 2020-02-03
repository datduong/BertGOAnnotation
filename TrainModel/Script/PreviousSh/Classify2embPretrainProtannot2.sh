
## using the newer code ... hopefully the fp16 works

## LM tune the data
# conda activate tensorflow_gpuenv
server='/local/datdb'
# data_dir=$server/'deepgo/data/DataToFinetuneBertTokenPredict/FinetunePhaseData'
mkdir $server/'deepgo/data/BertNotFtAARawSeqGO'

# pretrained_label_path='/local/datdb/deepgo/data/cosine.AveWordClsSep768.Linear768.Layer12/label_vector.pickle'
pretrained_label_path='/local/datdb/deepgo/data/BertAveL11L12D256/label_vector.pickle'

#ProtAnnotTypeTopo
choice='2embPpiAnnotE256H1L12I512Set0/YesPpiYesTypeScaleFreezeBert12Ep10e10Drop0.1' # Lr5e-5 Dr0.2
model_type='ppi'
cache_name='YesPpiYesType'
checkpoint=55440 ## 110726

block_size=1792 # mf and cc 1792 but bp has more term  2048
save_every=7000 # 9500 10000

batch_size=4

for ontology in 'mf' ; do # 'cc' 'bp'

  if [[ $ontology == 'bp' ]]
  then
    batch_size=4
    block_size=2048
    checkpoint=116144
  fi

  last_save=$server/'deepgo/data/BertNotFtAARawSeqGO/'$ontology/'fold_1'/$choice
  output_dir=$server/'deepgo/data/BertNotFtAARawSeqGO/'$ontology/'fold_1'/$choice
  mkdir $output_dir

  bert_vocab=$output_dir/'vocabAA.txt'
  config_name=$output_dir/config.json

  aa_type_file='/local/datdb/deepgo/data/train/fold_1/ProtAnnotTypeData/train_'$ontology'_prot_annot_type_count.pickle'

  train_masklm_data='/local/datdb/deepgo/data/train/fold_1/ProtAnnotTypeData/train-'$ontology'-input.tsv' ## okay to call it as long as it has ppi
  eval_data_file='/local/datdb/deepgo/data/train/fold_1/ProtAnnotTypeData/dev-'$ontology'-input.tsv'
  label_2test='/local/datdb/deepgo/data/train/deepgo.'$ontology'.csv'

  cd $server/BertGOAnnotationTrainModel/

  # continue training use @model_name_or_path and turn off @config_override
  CUDA_VISIBLE_DEVICES=4 python3 -u RunTokenClassifyProtData.py --cache_name $cache_name --block_size $block_size --mlm --bert_vocab $bert_vocab --train_data_file $train_masklm_data --output_dir $output_dir --num_train_epochs 100 --per_gpu_train_batch_size $batch_size --per_gpu_eval_batch_size 4 --config_name $config_name --do_train --model_type $model_type --overwrite_output_dir --save_steps $save_every --logging_steps $save_every --evaluate_during_training --eval_data_file $eval_data_file --label_2test $label_2test --learning_rate 0.0001 --seed 2019 --fp16 --config_override --pretrained_label_path $pretrained_label_path --aa_type_file $aa_type_file --reset_emb_zero > $output_dir/train_point.txt 
  ## --pretrained_label_path $pretrained_label_path --aa_type_file $aa_type_file --reset_emb_zero

  ## testing phase --pretrained_label_path $pretrained_label_path
  # for test_data in 'test' 'train'; do # 'dev'
  #   save_prediction='prediction_train_all_on_'$test_data

  #   eval_data_file='/local/datdb/deepgo/data/train/fold_1/ProtAnnotTypeData/'$test_data'-'$ontology'-input.tsv' 

  #   CUDA_VISIBLE_DEVICES=1 python3 -u RunTokenClassifyProtData.py --save_prediction $save_prediction --cache_name $cache_name --block_size $block_size --mlm --bert_vocab $bert_vocab --train_data_file $train_masklm_data --output_dir $output_dir --per_gpu_eval_batch_size $batch_size --config_name $config_name --do_eval --model_type $model_type --overwrite_output_dir --evaluate_during_training --eval_data_file $eval_data_file --label_2test $label_2test --config_override --eval_all_checkpoints --checkpoint $checkpoint --pretrained_label_path $pretrained_label_path --aa_type_file $aa_type_file --reset_emb_zero > $output_dir/'eval_'$test_data'_check_point.txt'
  # done  # --pretrained_label_path $pretrained_label_path --aa_type_file $aa_type_file --reset_emb_zero

done


