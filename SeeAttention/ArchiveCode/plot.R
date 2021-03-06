
library('dendextend', help, pos = 2, lib.loc = NULL)
library(RColorBrewer)
graphics.off() 
coul <- colorRampPalette(brewer.pal(8, "PiYG"))(25)

get_cluster = function(df,cut_k=2) {
  dendrogram = hclust(dist(df))
  dendrogram_group = cutree(dendrogram,k=cut_k) ## get group 
  dendrogram_group = sort(dendrogram_group)
  dendrogram_name = names(dendrogram_group)
  return (list(dendrogram,dendrogram_group,dendrogram_name))
}

get_top_contributor = function (df,row){
  z = df[row,]
  return ( rownames(df) [ which ( z > quantile ( z, .9) ) ] ) 
}

# setwd('C:/Users/dat/Documents/BertNotFtAARawSeqGO/fold_1mf_relu/')

setwd('/u/scratch/d/datduong/deepgo/data/BertNotFtAARawSeqGO/fold_1mf2embGelu/')

high_cooccur = unlist( strsplit ( 'GO:0072509 GO:0004857 GO:0032555 GO:0000166 GO:0004857 GO:0000166 GO:0005216 GO:0004857 GO:0005525 GO:0004857 GO:0050839 GO:0000166', " " ) )
high_cooccur = gsub(":","",unique(high_cooccur)) 


for (num in 0:5){
  # num=5
  df = read.csv ( paste0('GO2GO_attention_head',num,'.csv'), header=T )
  # df = read.csv ( paste0('GO2GO_attention_ave_head.csv'), header=T )  
  df = as.matrix (df)
  rownames(df) = paste0('',colnames(df))
  # df = df[1:50,1:50] ## subset just to see 
  df = df [ ! rownames(df) %in% high_cooccur , ! colnames(df) %in% high_cooccur ]
  pdf (paste0('Head',num,'.pdf'),height=7,width=8) # first50
  heatmap(df,scale="none",col = coul,Colv=NA,main=paste('Head',num))
  dev.off() 
  # p1 = heatmap(df,scale="none",col = coul,Colv=NA,main=paste('ave',num))
}

# rownames(df)[10]
# get_top_contributor(df,10)
# graphics.off() 


# cooccur = read.csv ( 'C:/Users/dat/Documents/GO2GO_mf_count.csv', header=T )  
cooccur = read.csv ( '/u/scratch/d/datduong/deepgo/data/train/fold_1/TokenClassify/GO2GO_mf_count.csv', header=T )  

cooccur = as.matrix (cooccur)
rownames(cooccur) = colnames(cooccur)
cooccur = cooccur / colSums(cooccur) ## R divide down the row
cooccur[is.nan(cooccur)] = 0 
cooccur = cooccur [ ! rownames(cooccur) %in% high_cooccur , ! colnames(cooccur) %in% high_cooccur ]
# cooccur = cooccur[1:50,1:50]
pdf (paste0('coocurrFirst50.pdf'),height=7,width=8)
heatmap(cooccur,scale="none",col = coul,Colv=NA,main='Co-occurrence')
dev.off() 

cooccur_group = get_cluster(cooccur,4)


for (num in c(0:5)) {
  df = read.csv ( paste0('GO2GO_attention_head',num,'.csv'), header=T )
  df = as.matrix (df)
  rownames(df) = paste0('',colnames(df))
  # df = df[1:50,1:50] ## subset just to see 
  df_group = get_cluster(df,4)
  # df_group[[2]]
  # df_group[[3]]
  print (paste0('head ',num))
  print (dendlist(as.dendrogram(df_group[[1]]), as.dendrogram(cooccur_group[[1]])) %>% untangle(method = "step1side") %>% entanglement() )
  # ent = entanglement (as.dendrogram(df_group[[1]]), as.dendrogram(cooccur_group[[1]]))
  # print (ent)
  print (cor_cophenetic(as.dendrogram(df_group[[1]]), as.dendrogram(cooccur_group[[1]])))
}
# tanglegram(dl)


relu 
[1] 0.6135558
[1] 0.6103813
[1] 0.6778977
[1] 0.7205237
[1] 0.6783651
[1] 0.7430645

[1] 0.3535921
[1] 0.3005707
[1] 0.2775146
[1] 0.3023639
[1] 0.2899833
[1] 0.2807402

[1] 0.296925 correlation 
[1] 0.2987238
[1] 0.2409891
[1] 0.3854294
[1] 0.3730905
[1] 0.5327675


gelu 
[1] 0.3525503
[1] 0.4241359
[1] 0.7189362
[1] 0.6376364
[1] 0.75702
[1] 0.7171842

[1] 0.2930331
[1] 0.3140639
[1] 0.2800639
[1] 0.4119118
[1] 0.3083879
[1] 0.3585995

[1] 0.4988198 correlation
[1] 0.2338982
[1] 0.2963654
[1] 0.02816023
[1] 0.5428462
[1] 0.01679081


# Get lower triangle of the correlation matrix
get_lower_tri<-function(cormat){
  cormat[upper.tri(cormat)] <- NA
  return(cormat)
}
# Get upper triangle of the correlation matrix
get_upper_tri <- function(cormat){
  cormat[lower.tri(cormat)]<- NA
  return(cormat)
}

library('ggplot2')
library('reshape2')
make_heatmap_ggplot = function (df) {
  melted_cormat <- melt(df)
  ggplot(data = melted_cormat, aes(x=Var1, y=Var2, fill=value)) + geom_tile() + theme(axis.text.x = element_text(angle = 45, hjust = 1))
}

windows()
make_heatmap_ggplot(df)
windows()
make_heatmap_ggplot(cooccur)







q()

ave_downward = function(fin,num_label,direction){
  ## compute some summary statistics on best "aa"
  total_len = nrow(fin)
  down = apply(fin,direction,quantile,c(0.25,.5,.75))
  return (down)
}

# p='P23109'
layer = 0
num_label = 589
# prot = 'O54992 P23109 P9WNC3' # 'B3PC73 O54992 P23109'# 'P23109' # B3PC73 O54992 P23109
# prot = strsplit(prot,"\\s+")[[1]]
prot = 'O54992 P23109 P9WNC3'
prot = strsplit(prot,"\\s+")[[1]]
for (name in c('layerAA2AA','layerAA2all')){ # ,'layerAA2all','layerAA2GO'
  for (p in prot){
    pdf(paste0(p,name,'_JtoI.pdf'),width=18, height=12)
    # par(mfrow=c(6,4))
    par(mfrow=c(4,3))
    for (layer in 0:11) {
      fin = read.csv( paste0(p , 'layer' , layer, 'head',0,'.csv'), header=F )
      fin = as.matrix(fin)
      num_aa = nrow(fin)-num_label-2 ## CLS and SEP
      fin = fin [,-1*c(1,num_aa+2)] ## remove the weights toward CLS and SEP ?
      fin = fin [-1*c(1,num_aa+2),] ## remove the weights by CLS and SEP ?

      # fin = log ( fin * 1000 )

      if (name == 'layerAA2AA'){
        fin = fin [1:num_aa, 1:num_aa] ## get contribution of aa toward all the aa itself
        z = ave_downward (fin,num_label,2)
      } else if ( name=='layerAA2GO') {
        fin = fin [1:num_aa, (num_aa+1):ncol(fin) ] ## get contribution AA --> GO
      } else if ( name=='layerAA2all') {
        fin = fin [1:num_aa, ] ## get contribution toward all the signals
        z = ave_downward (fin,num_label,2)
      } else {
        fin = fin [(num_aa+1):nrow(fin), ] ## when look at labels, what contribute the most ?
        z = ave_downward (fin,num_label,2)
      }

      print (p)

      if (layer==0){
        plot(1:ncol(z), z[2,], pch=16,cex=.5, type='l', main=paste(p,'layer',layer), xlab='index',ylab='prob',ylim=c(0,1/(num_aa+num_label)+.01))
      } else {
        plot(1:ncol(z), z[2,], pch=16,cex=.5, type='l', main=paste(p,'layer',layer), xlab='index',ylab='prob')
      }
      abline(h = 1/(num_aa+num_label), col='blue' )
      abline(v = c(51,115,182,337), col='red', lty=2 )
      abline(v = num_aa+1, col='green', lty=2 )

    }
    dev.off()
  }
}

##




# png (file = paste0(p,'h0h1.png'),width=30, height=10, units='in', res = 400)
# grid.arrange(grobs = plot_list, ncol=10, nrow=2) ## display plot
# # ggsave(file = paste0(p,'.png'), arrangeGrob(grobs = plot_list, ncol=4, nrow=10), width=30, height=10, units='in')  ## save plot
# dev.off()


B3PC73 732
s="MSTFARLFLCLVFFASLQPAMAQTEDGYDMWLRYQPIADQTLLKTYQKQIRHLHVAGDSPTINAAAAELQRGLSGLLNKPIVARDEKLKDYSLVIGTPDNSPLIASLNLGERLQALGAEGYLLEQTRINKRHVVIVAANSDVGVLYGSFHLLRLIQTQHALEKLSLSSAPRLQHRVVNHWDNLNRVVERGYAGLSLWDWGSLPNYLAPRYTDYARINASLGINGTVINNVNADPRVLSDQFLQKIAALADAFRPYGIKMYLSINFNSPRAFGDVDTADPLDPRVQQWWKTRAQKIYSYIPDFGGFLVKADSEGQPGPQGYGRDHAEGANMLAAALKPFGGVVFWRAFVYHPDIEDRFRGAYDEFMPLDGKFADNVILQIKNGPIDFQPREPFSALFAGMSRTNMMMEFQITQEYFGFATHLAYQGPLFEESLKTETHARGEGSTIGNILEGKVFKTRHTGMAGVINPGTDRNWTGHPFVQSSWYAFGRMAWDHQISAATAADEWLRMTFSNQPAFIEPVKQMMLVSREAGVNYRSPLGLTHLYSQGDHYGPAPWTDDLPRADWTAVYYHRASKTGIGFNRTKTGSNALAQYPEPIAKAWGDLNSVPEDLILWFHHLSWDHRMQSGRNLWQELVHKYYQGVEQVRAMQRTWDQQEAYVDAARFAQVKALLQVQEREAVRWRNSCVLYFQSVAGRPIPANYEQPEHDLEYYKMLARTTYVPEPWHPASSSRVLK"
s[0 : 732//2]
s[732//2 : 732]


s[0:250]
'MSTFARLFLCLVFFASLQPAMAQTEDGYDMWLRYQPIADQTLLKTYQKQIRHLHVAGDSPTINAAAAELQRGLSGLLNKPIVARDEKLKDYSLVIGTPDNSPLIASLNLGERLQALGAEGYLLEQTRINKRHVVIVAANSDVGVLYGSFHLLRLIQTQHALEKLSLSSAPRLQHRVVNHWDNLNRVVERGYAGLSLWDWGSLPNYLAPRYTDYARINASLGINGTVINNVNADPRVLSDQFLQKIAALAD'
s[250::]
'AFRPYGIKMYLSINFNSPRAFGDVDTADPLDPRVQQWWKTRAQKIYSYIPDFGGFLVKADSEGQPGPQGYGRDHAEGANMLAAALKPFGGVVFWRAFVYHPDIEDRFRGAYDEFMPLDGKFADNVILQIKNGPIDFQPREPFSALFAGMSRTNMMMEFQITQEYFGFATHLAYQGPLFEESLKTETHARGEGSTIGNILEGKVFKTRHTGMAGVINPGTDRNWTGHPFVQSSWYAFGRMAWDHQISAATAADEWLRMTFSNQPAFIEPVKQMMLVSREAGVNYRSPLGLTHLYSQGDHYGPAPWTDDLPRADWTAVYYHRASKTGIGFNRTKTGSNALAQYPEPIAKAWGDLNSVPEDLILWFHHLSWDHRMQSGRNLWQELVHKYYQGVEQVRAMQRTWDQQEAYVDAARFAQVKALLQVQEREAVRWRNSCVLYFQSVAGRPIPANYEQPEHDLEYYKMLARTTYVPEPWHPASSSRVLK'

p = "5   6   8  13  15  29  32  35  38  47  52  66  67  71  79  80  88  89
100 105 114 116 124 128 133 135 139 144 146 160 164 169 177 181 186 187
191 192 194 195 197 199 203 205 211 214 234 237 239 246 248 251 254 255
256 257 258 261 262 264 266 272 273 275 276 279 281 290 294 296 299 306
310 311 312 321 323 325 326 332 333 336 339 341 343 345 348 349 350 353
354 356 357 359 360 363 365 370 372 376 378 380 383 385 386 387 388 389
393 397 398 399 401 402 407 409 410 413 416 417 418 424 425 426 427 429
433 434 441 442 446 447 450 454 455 458 460 464 466 472 477 480 484 485
486 487 488 498 499 501 510 514 516 517 519 521 522 524 531 534 542 544
547 548 552 554 555 564 566 567 568 569 570 571 576 581 583 585 590 592
593 596 597 600 605 606 613 619 624 627 629 630 631 637 638 640 641 642
643 645 646 647 652 653 655 657 661 675 679 681 684 685 687 688 689 700
705 710 718 723 "
p = strsplit(p,"\\s+")[[1]]
hist(as.numeric(p),breaks=15)


473
s = """
MSEDSDMEKAIKETSILEEYSINWTQKLGAGISGPVRVCVKKSTQERFALKILLDRPKARNEVRLHMMCATHPNIVQIIEVFANSVQFPHESSPRARLLIVMEMMEGGELFHRISQHRHFTEKQASQVTKQIALALQHCHLLNIAHRDLKPENLLFKDNSLDAPVKLCDFGFAKVDQGDLMTPQFTPYYVAPQVLEAQRRHQKEKSGIIPTSPTPYTYNKSCDLWSLGVIIYVMLCGYPPFYSKHHSRTIPKDMRKKIMTGSFEFPEEEWSQISEMAKDVVRKLLKVKPEERLTIEGVLDHPWLNSTEALDNVLPSAQLMMDKAVVAGIQQAHAEQLANMRIQDLKVSLKPLHSVNNPILRKRKLLGTKPKDGIYIHDHENGTEDSNVALEKLRDVIAQCILPQAGKGENEDEKLNEVMQEAWKYNRECKLLRDALQSFSWNGRGFTDKVDRLKLAEVVKQVIEEQTLPHEPQ
""".strip()
import numpy as np
import re
s = re.sub(r"\n","",s)
for i in np.arange(0,473,100):
  # print ('\n'+str(i))
  if i+100 < 473:
    print(">a{}".format(i))
    print(s[i:i+100])
  else:
    print(">a{}".format(i))
    print (s[i:473])


s[0:250]
s[250::]

>>> s[0:250]
'MSEDSDMEKAIKETSILEEYSINWTQKLGAGISGPVRVCVKKSTQERFALKILLDRPKARNEVRLHMMCATHPNIVQIIEVFANSVQFPHESSPRARLLIVMEMMEGGELFHRISQHRHFTEKQASQVTKQIALALQHCHLLNIAHRDLKPENLLFKDNSLDAPVKLCDFGFAKVDQGDLMTPQFTPYYVAPQVLEAQRRHQKEKSGIIPTSPTPYTYNKSCDLWSLGVIIYVMLCGYPPFYSKHHSRTI'
>>>
>>> s[250::]
'PKDMRKKIMTGSFEFPEEEWSQISEMAKDVVRKLLKVKPEERLTIEGVLDHPWLNSTEALDNVLPSAQLMMDKAVVAGIQQAHAEQLANMRIQDLKVSLKPLHSVNNPILRKRKLLGTKPKDGIYIHDHENGTEDSNVALEKLRDVIAQCILPQAGKGENEDEKLNEVMQEAWKYNRECKLLRDALQSFSWNGRGFTDKVDRLKLAEVVKQVIEEQTLPHEPQ'
>>>


"".join( s[z] for z in p )

d = "1   5   6  10  12  21  30  32  33  37  51  52  58  71  73  74  77  80
  89  91  92  93  97 101 103 105 107 108 109 110 113 114 126 131 133 138
 140 142 151 155 157 162 163 175 177 180 190 192 198 204 210 224 230 231
 232 233 238 239 241 247 251 252 256 257 259 260 261 264 266 267 273 278
 279 282 287 288 289 298 299 310 312 319 326 327 330 331 333 335 343 345
 347 354 356 358 360 361 363 366 371 372 374 375 376 377 382 383 386 389
 390 392 396 397 398 399 402 406 407 409 413 415 417 419 420 421 423 424
 425 426 430 431 436 439 442 443 449 455 457 459 460 461 463 464 470    "
d = as.numeric(strsplit(d,"\\s+")[[1]])
hist(d,breaks=15)


YPNEAAVSKDEPKPLPYPNLDTFLDDMNFLLALIAQGPVKTYTHRRLKFLSSKFQVHQMLNEMDELKELKNNPHRDFYNCRKVDTHIHAAACMNQKHLLR
FIKKSYQIDADRVVYSTKEKNLTLKELFAKLKMHPYDLTVDSLDVHAGRQTFQRFDKFNDKYNPVGASELRDLYLKTDNYINGEYFATIIKEVGADLVEA
KYQHAEPRLSIYGRSPDEWSKLSSWFVCNRIHCPNMTWMIQVPRIYDVFRSKNFLPHFGKMLENIFMPVFEATINPQADPELSVFLKHITGFDSVDDESK
HSGHMFSSKSPKPQEWTLEKNPSYTYYAYYMYANIMVLNSLRKERGMNTF

P23109 780
s="""MNVRIFYSVSQSPHSLLSLLFYCAILESRISATMPLFKLPAEEKQIDDAMRNFAEKVFAS
EVKDEGGRQEISPFDVDEICPISHHEMQAHIFHLETLSTSTEARRKKRFQGRKTVNLSIP
LSETSSTKLSHIDEYISSSPTYQTVPDFQRVQITGDYASGVTVEDFEIVCKGLYRALCIR
EKYMQKSFQRFPKTPSKYLRNIDGEAWVANESFYPVFTPPVKKGEDPFRTDNLPENLGYH
LKMKDGVVYVYPNEAAVSKDEPKPLPYPNLDTFLDDMNFLLALIAQGPVKTYTHRRLKFL
SSKFQVHQMLNEMDELKELKNNPHRDFYNCRKVDTHIHAAACMNQKHLLRFIKKSYQIDA
DRVVYSTKEKNLTLKELFAKLKMHPYDLTVDSLDVHAGRQTFQRFDKFNDKYNPVGASEL
RDLYLKTDNYINGEYFATIIKEVGADLVEAKYQHAEPRLSIYGRSPDEWSKLSSWFVCNR
IHCPNMTWMIQVPRIYDVFRSKNFLPHFGKMLENIFMPVFEATINPQADPELSVFLKHIT
GFDSVDDESKHSGHMFSSKSPKPQEWTLEKNPSYTYYAYYMYANIMVLNSLRKERGMNTF
LFRPHCGEAGALTHLMTAFMIADDISHGLNLKKSPVLQYLFFLAQIPIAMSPLSNNSLFL
EYAKNPFLDFLQKGLMISLSTDDPMQFHFTKEPLMEEYAIAAQVFKLSTCDMCEVARNSV
LQCGISHEEKVKFLGDNYLEEGPAGNDIRRTNVAQIRMAYRYETWCYELNLIAEGLKSTE"""
import numpy as np
import re
s = re.sub(r"\n","",s)
for i in np.arange(0,700,50):
  print ('\n'+str(i))
  if i+50 < 780:
    print(s[i:i+50])
  else:
    print (s[i:780])

d = "5   8  10  23  27  35  36  54  77  80  82  83  91  93 104 108 110 113
121 132 133 134 140 141 143 152 156 158 162 163 164 166 168 169 179 180
181 183 184 192 199 204 205 207 210 211 213 221 223 224 235 239 240 246
248 249 252 253 256 257 261 262 263 265 267 269 274 275 277 278 279 280
283 285 286 288 290 291 293 295 314 315 324 325 327 329 331 332 334 335
336 338 342 343 344 347 348 352 354 357 359 360 361 362 363 364 367 369
372 382 386 387 394 395 396 397 398 399 403 409 410 413 417 418 421 425
426 427 430 434 436 437 438 439 441 445 446 449 453 463 464 466 467 470
472 477 478 481 483 484 485 486 490 491 493 496 497 499 504 507 508 510
516 518 519 520 523 528 530 531 533 535 538 539 542 545 546 547 551 552
556 557 562 572 573 575 576 577 579 581 583 584 587 588 590 592 600 606
608 616 617 619 621 629 630 633 639 640 641 647 662 666 667 674 675 679
683 685 688 700 717 718 719 721 725 732 746 754 755 761 766 768 773 776
782"
d = as.numeric(strsplit(d,"\\s+")[[1]])
windows()
hist(d,breaks=15)

