
/usr/local/cuda-10.1/bin
export PATH="/usr/local/cuda-10.1/bin:$PATH"

. /u/local/Modules/default/init/modules.sh
module load python/3.7.2

#### load back test file, eval on different groups of GOs
main_dir='/u/scratch/d/datduong/deepgo/data/BertNotFtAARawSeqGO/'
for run_type in YesPpi100YesTypeScaleFreezeBert12Ep10e10Drop0.1 NoPpiYesTypeScaleFreezeBert12Ep10e10Drop0.1 YesPpiYesTypeScaleFreezeBert12Ep10e10Drop0.1 ; do
  method='/fold_1/2embPpiAnnotE256H1L12I512Set0/'$run_type'/'
  code_dir='/u/scratch/d/datduong/BertGOAnnotation/AnalyzeGoVec'
  out_dir='/u/scratch/d/datduong/deepgo/data/BertNotFtAARawSeqGO/EvalLabelByGroup'
  mkdir $out_dir
  cd $code_dir
  python3 AnalyzeGoTypeAccuracy.py $main_dir $method > $out_dir/$run_type.txt
done
cd $out_dir




#### load back test file, eval on different groups of GOs Run on a much more finer split on fmax
main_dir='/u/scratch/d/datduong/deepgo/data/BertNotFtAARawSeqGO/'
method='/fold_1/2embPpiAnnotE256H1L12I512Set0/YesPpiYesTypeScaleFreezeBert12Ep10e10Drop0.1/'
code_dir='/u/scratch/d/datduong/BertGOAnnotation/AnalyzeGoVec'
out_dir='/u/scratch/d/datduong/deepgo/data/BertNotFtAARawSeqGO/EvalLabelByGroup'
mkdir $out_dir
cd $code_dir
python3 AnalyzeGoTypeAccuracy.py $main_dir $method > $out_dir/ZeroshotYesPpiYesTypeDeepGOOriginData.txt
cd $out_dir


#### use blast to eval added term... not pure zeroshot


. /u/local/Modules/default/init/modules.sh
module load python/3.7.2
for method in blastPsiblastResultEval10 blastPsiblastResultEval100 ; do 
  out_dir='/u/scratch/d/datduong/deepgo/dataExpandGoSet/train/fold_1/'$method
  main_dir='/u/scratch/d/datduong/deepgo/data/BertNotFtAARawSeqGO/'
  code_dir='/u/scratch/d/datduong/BertGOAnnotation/AnalyzeGoVec'
  cd $code_dir
  python3 AnalyzeGoTypeAccuracyBlast.py $main_dir $method > $out_dir/$method.txt
  cd $out_dir
done

