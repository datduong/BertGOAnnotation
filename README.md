# GOAT: GO Annotation with the Transformer model 

### [This is our paper.](https://www.biorxiv.org/content/10.1101/2020.01.31.929604v1)

### Libraries needed

[pytorch](https://pytorch.org/),
[pytorch-transformers](https://pypi.org/project/pytorch-transformers/),
[nvidia-apex](https://github.com/NVIDIA/apex)

## Where are pre-trained models? 

We adapt the Transformer neural network model to predict GO labels for protein sequences. We trained our method on [DeepGO datasets](https://github.com/bio-ontology-research-group/deepgo#data) which was used as a baseline in our paper.
You can download **[our trained models here](https://drive.google.com/drive/folders/1MfjpaZ4Mg0L6PovPzfjAlB_ny1zYFFNm?usp=sharing)**. 

During training, we saved the model at each checkpoint. Once we finished, we kept only checkpoint that works best with the dev datasets. You will see these saved files in the format [checkpoint-number](https://drive.google.com/drive/folders/128Q5DBToXnpgBNpevuYv3Y403wIPj8r-?usp=sharing). 

The [config.json](https://drive.google.com/drive/folders/128Q5DBToXnpgBNpevuYv3Y403wIPj8r-?usp=sharing) shows how the Transformer model was trained. Please see this **[demo script](https://github.com/datduong/GOAnnotationTransformer/tree/master/TrainModel)** that shows to use a trained model to evaluate a test set, and how to explore some of the model properties. 


## How to train your model?

You can **[train your own model](https://github.com/datduong/GOAnnotationTransformer/tree/master/TrainModel)**. Your **[input must match the input here.](https://drive.google.com/drive/u/1/folders/10mKp6vOzU9_3SYJ2Bd_NfqQ6ILjTJfXo)** The high-level format is 

protein_name \t sequence \t label \t protein_vector_from_external_source \t domain_motif_in_sequence

**We support 4 training options:**
1. Base Transformer
2. Domain data (like motifs, compositional bias, etc.)
3. External protein data (like 3D structure, protein-protein interaction network)
4. Any combination of the above. 

You can download the most updated manually annotated data at [Uniprot.org](https://www.uniprot.org/uniprot/?query=reviewed:yes). The site also provides all known motifs and domains for a given sequence. You may have to do a [custom download from Uniprot](https://www.uniprot.org/uniprot/?query=reviewed:yes#customize-columns) for these extra information. 

We do not have the pre-trained encoder in DeepGO that provides embeddings for any proteins in a protein-protein interaction network. 

We do have the pre-trained encoder that provides embeddings representing 3D structures of proteins. 


