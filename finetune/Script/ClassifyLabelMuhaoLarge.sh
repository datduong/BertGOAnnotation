
# conda activate tensorflow_gpuenv
server='/local/datdb'
mkdir $server/'deepgo/data/BertNotFtAARawSeqGO'

pretrained_label_path='/local/datdb/deepgo/data/cosine.AveWordClsSep768.Linear256.Layer12/label_vector.pickle'

choice='2embPpiAnnotE256H1L12I512Set0/ProtAnnotTypeLarge/YesPpiMuhaoYesTypeScaleFreezeBert12Ep10e10Drop0.1' # Lr5e-5 Dr0.2
model_type='ppi' ####
cache_name='YesPpiYesType' ## !! okay to use the same pre-processed data
checkpoint=30240

block_size=2816 # mf and cc 1792 but bp has more term 2048
save_every=7000

batch_size=4
seed=2019  ####

for ontology in 'mf' ; do # 'cc' 'bp'

  if [[ $ontology == 'cc' ]]
  then
    seed=2020 #### we switch seed so that we can train at batch=4 ... doesn't matter really
    batch_size=4
    block_size=2816
    checkpoint=71090
  fi

  if [[ $ontology == 'bp' ]]
  then
    seed=2019
    batch_size=4
    block_size=4048
    checkpoint=65475
  fi

  last_save=$server/'deepgo/data/BertNotFtAARawSeqGO/'$ontology/'fold_1'/$choice ##!! not change output when use larger data
  output_dir=$server/'deepgo/data/BertNotFtAARawSeqGO/'$ontology/'fold_1'/$choice ##!! not change output when use larger data
  mkdir $output_dir

  bert_vocab=$output_dir/'vocabAA.txt'
  config_name=$output_dir/config.json

  aa_type_file='/local/datdb/deepgo/dataExpandGoSet/train/fold_1/ProtAnnotTypeData/train_'$ontology'_prot_annot_type_count.pickle'

  train_masklm_data='/local/datdb/deepgo/dataExpandGoSet/train/fold_1/ProtAnnotTypeData/train-'$ontology'-input-muhao.tsv' ## okay to call it as long as it has ppi
  eval_masklm_data='/local/datdb/deepgo/dataExpandGoSet/train/fold_1/ProtAnnotTypeData/dev-'$ontology'-input-muhao.tsv'
  label_2test='/local/datdb/deepgo/dataExpandGoSet/train/deepgo.'$ontology'.csv'

  cd $server/BertGOAnnotation/finetune/

  #### train the model
  # continue training use @model_name_or_path and turn off @config_override
  CUDA_VISIBLE_DEVICES=1 python3 -u RunTokenClassifyProtData.py --cache_name $cache_name --block_size $block_size --mlm --bert_vocab $bert_vocab --train_data_file $train_masklm_data --output_dir $output_dir --num_train_epochs 100 --per_gpu_train_batch_size $batch_size --per_gpu_eval_batch_size 2 --config_name $config_name --do_train --model_type $model_type --overwrite_output_dir --save_steps $save_every --logging_steps $save_every --evaluate_during_training --eval_data_file $eval_masklm_data --label_2test $label_2test --learning_rate 0.0001 --seed $seed --fp16 --config_override --pretrained_label_path $pretrained_label_path --aa_type_file $aa_type_file --reset_emb_zero > $output_dir/train_point.txt
  ## --pretrained_label_path $pretrained_label_path --aa_type_file $aa_type_file --reset_emb_zero

  ## COMMENT testing phase
  # for test_data in 'test'  ; do # 'dev'

  #   #### normal testing on same set of labels
  #   # save_prediction='prediction_train_all_on_'$test_data
  #   # eval_masklm_data='/local/datdb/deepgo/dataExpandGoSet/train/fold_1/ProtAnnotTypeData/'$test_data'-'$ontology'-input-muhao.tsv'
  #   # CUDA_VISIBLE_DEVICES=7 python3 -u RunTokenClassifyProtData.py --save_prediction $save_prediction --cache_name $cache_name --block_size $block_size --mlm --bert_vocab $bert_vocab --train_data_file $train_masklm_data --output_dir $output_dir --per_gpu_eval_batch_size $batch_size --config_name $config_name --do_eval --model_type $model_type --overwrite_output_dir --evaluate_during_training --eval_data_file $eval_masklm_data --label_2test $label_2test --config_override --eval_all_checkpoints --checkpoint $checkpoint --pretrained_label_path $pretrained_label_path --aa_type_file $aa_type_file --reset_emb_zero > $output_dir/'eval_'$test_data'_check_point.txt'

  #   #### do zeroshot on larger set
  #   save_prediction='save_prediction_expand'
  #   eval_masklm_data='/local/datdb/deepgo/dataExpandGoSet/train/fold_1/ProtAnnotTypeData/'$test_data'-'$ontology'-input-muhao.tsv'
  #   label_2test='/local/datdb/deepgo/dataExpandGoSet/train/deepgo.'$ontology'.csv' ## COMMENT larger label set

  #   ##!!##!!

  #   new_num_labels=1697 ##!! COMMENT more labels
  #   block_size=2816 ##!! COMMENT zeroshot need larger block size because more labels

  #   if [[ $ontology == 'cc' ]]
  #   then
  #     new_num_labels=989
  #     block_size=2816
  #   fi

  #   if [[ $ontology == 'bp' ]]
  #   then
  #     new_num_labels=2980
  #     block_size=4048
  #   fi

  #   model_name_or_path=$output_dir/'checkpoint-'$checkpoint ##!!##!! load in checkpoint, then replace emb for correct size

  #   CUDA_VISIBLE_DEVICES=7 python3 -u RunTokenClassifyProtData.py --model_name_or_path $model_name_or_path --new_num_labels $new_num_labels --save_prediction $save_prediction --cache_name $cache_name --block_size $block_size --mlm --bert_vocab $bert_vocab --train_data_file $train_masklm_data --output_dir $output_dir --per_gpu_eval_batch_size $batch_size --config_name $config_name --do_eval --model_type $model_type --overwrite_output_dir --evaluate_during_training --eval_data_file $eval_masklm_data --label_2test $label_2test --config_override --eval_all_checkpoints --checkpoint $checkpoint --pretrained_label_path $pretrained_label_path --aa_type_file $aa_type_file --reset_emb_zero > $output_dir/'eval_'$test_data'_expand.txt'
  # done

done



# --pretrained_label_path $pretrained_label_path --aa_type_file $aa_type_file --reset_emb_zero $output_dir/'eval_'$test_data'_expand.txt'

