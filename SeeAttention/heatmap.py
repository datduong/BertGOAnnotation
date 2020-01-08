
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
import pickle,re,sys,os
import pandas as pd

# path = '/local/datdb/deepgo/data/BertNotFtAARawSeqGO/mf/fold_1/2embPpiGeluE768H1L12I768PretrainLabelDrop0.1/ManualValidate/'

path = '/local/datdb/deepgo/data/BertNotFtAARawSeqGO/mf/fold_1/2embPpiAnnotE256H1L12I512Set0/NoPpiYesTypeScaleFreezeBert12Ep10e10Drop0.1/SeeAttention'

list_prot_to_get = pd.read_csv('/local/datdb/BertGOAnnotation/SeeAttention/name_get_attention_test.tsv',header=None)
list_prot_to_get = sorted(list(list_prot_to_get[0]))

os.chdir(path)
to_load = os.listdir(path)
for name in to_load:
  if 'pickle' not in name:
    continue
  protn = re.sub(r'_attention_value\.pickle','',name)
  if protn not in list_prot_to_get:
    continue
  #
  attention = pickle.load (open(name,"rb"))
  #
  prot = list ( attention.keys() ) ## just 1 thing by itself
  if not os.path.exists(prot[0]):
    os.mkdir(prot[0])
  print (prot)
  for p in prot:
    for layer in range(12):
      for head in range (1):
        matrix = attention[p] [layer] [head]
        np.savetxt (  p + '/' + p + '_layer_' + str(layer) + '_head_' + str(head)+'.csv', matrix, delimiter=',')




# for p in prot:
#   for layer in range(10):
#     for head in range (4):
#       matrix = attention[p] [layer] [head]
#       plt.clf()
#       plt.imshow(matrix,interpolation='nearest', cmap=cm.inferno)
#       # ax.colorbar() # Add a scale bar
#       # plt.title(p + ' layer ' + str(layer) + ' head ' + str(head))
#       plt.savefig( p + 'layer' + str(layer) + 'head' + str(head)+'.png' )

s = """
MVRPVRHKKPVNYSQFDHSDSDDDFVSATVPLNKKSRTAPKELKQDKPKPNLNNLRKEEI
PVQEKTPKKRLPEGTFSIPASAVPCTKMALDDKLYQRDLEVALALSVKELPTVTTNVQNS
QDKSIEKHGSSKIETMNKSPHISNCSVASDYLDLDKITVEDDVGGVQGKRKAASKAAAQQ
RKILLEGSDGDSANDTEPDFAPGEDSEDDSDFCESEDNDEDFSMRKSKVKEIKKKEVKVK
SPVEKKEKKSKSKCNALVTSVDSAPAAVKSESQSLPKKVSLSSDTTRKPLEIRSPSAESK
KPKWVPPAASGGSRSSSSPLVVVSVKSPNQSLRLGLSRLARVKPLHPNATST""".strip()
import numpy as np
import re
s = re.sub(r"\n","",s)


# GO:0019239;GO:0016814;GO:0016810;GO:0016787;GO:0003824

## !! no template found
>sp|Q96B01|R51A1_HUMAN RAD51-associated protein 1 OS=Homo sapiens OX=9606 GN=RAD51AP1 PE=1 SV=1
MVRPVRHKKPVNYSQFDHSDSDDDFVSATVPLNKKSRTAPKELKQDKPKPNLNNLRKEEI
PVQEKTPKKRLPEGTFSIPASAVPCTKMALDDKLYQRDLEVALALSVKELPTVTTNVQNS
QDKSIEKHGSSKIETMNKSPHISNCSVASDYLDLDKITVEDDVGGVQGKRKAASKAAAQQ
RKILLEGSDGDSANDTEPDFAPGEDSEDDSDFCESEDNDEDFSMRKSKVKEIKKKEVKVK
SPVEKKEKKSKSKCNALVTSVDSAPAAVKSESQSLPKKVSLSSDTTRKPLEIRSPSAESK
KPKWVPPAASGGSRSSSSPLVVVSVKSPNQSLRLGLSRLARVKPLHPNATST

## uniform match
>sp|P0A812|RUVB_ECOLI Holliday junction ATP-dependent DNA helicase RuvB OS=Escherichia coli (strain K12) OX=83333 GN=ruvB PE=1 SV=1
MIEADRLISAGTTLPEDVADRAIRPKLLEEYVGQPQVRSQMEIFIKAAKLRGDALDHLLI
FGPPGLGKTTLANIVANEMGVNLRTTSGPVLEKAGDLAAMLTNLEPHDVLFIDEIHRLSP
VVEEVLYPAMEDYQLDIMIGEGPAARSIKIDLPPFTLIGATTRAGSLTSPLRDRFGIVQR
LEFYQVPDLQYIVSRSARFMGLEMSDDGALEVARRARGTPRIANRLLRRVRDFAEVKHDG
TISADIAAQALDMLNVDAEGFDYMDRKLLLAVIDKFFGGPVGLDNLAAAIGEERETIEDV
LEPYLIQQGFLQRTPRGRMATTRAWNHFGITPPEMP

# Q6X632 # begin part is important
>sp|Q6X632|GPR75_MOUSE Probable G-protein coupled receptor 75 OS=Mus musculus OX=10090 GN=Gpr75 PE=1 SV=1
MNTSAPLQNVPNATLLNMPPLHGGNSTSLQEGLRDFIHTATLVTCTFLLAIIFCLGSYGN
FIVFLSFFDPSFRKFRTNFDFMILNLSFCDLFICGVTAPMFTFVLFFSSASSIPDSFCFT
FHLTSSGFVIMSLKMVAVIALHRLRMVMGKQPNCTASFSCILLLTLLLWATSFTLATLAT
LRTNKSHLCLPMSSLMDGEGKAILSLYVVDFTFCVAVVSVSYIMIAQTLRKNAQVKKCPP
VITVDASRPQPFMGASVKGNGDPIQCTMPALYRNQNYNKLQHSQTHGYTKNINQMPIPSA
SRLQLVSAINFSTAKDSKAVVTCVVIVLSVLVCCLPLGISLVQMVLSDNGSFILYQFELF
GFTLIFFKSGLNPFIYSRNSAGLRRKVLWCLRYTGLGFLCCKQKTRLRAMGKGNLEINRN
KSSHHETNSAYMLSPKPQRKFVDQACGPSHSKESAASPKVSAGHQPCGQSSSTPINTRIE
PYYSIYNSSPSQQESGPANLPPVNSFGFASSYIAMHYYTTNDLMQEYDSTSAKQIPIPSV

Q6FJA3 ## uniform match
>sp|Q6FJA3|PDC1_CANGA Pyruvate decarboxylase OS=Candida glabrata (strain ATCC 2001 / CBS 138 / JCM 3761 / NBRC 0622 / NRRL Y-65) OX=284593 GN=PDC1 PE=3 SV=1
MSEITLGRYLFERLNQVDVKTIFGLPGDFNLSLLDKIYEVEGMRWAGNANELNAAYAADG
YARIKGMSCIITTFGVGELSALNGIAGSYAEHVGVLHVVGVPSISSQAKQLLLHHTLGNG
DFTVFHRMSANISETTAMVTDIATAPAEIDRCIRTTYITQRPVYLGLPANLVDLKVPAKL
LETPIDLSLKPNDPEAETEVVDTVLELIKAAKNPVILADACASRHDVKAETKKLIDATQF
PSFVTPMGKGSIDEQHPRFGGVYVGTLSRPEVKEAVESADLILSVGALLSDFNTGSFSYS
YKTKNIVEFHSDYIKIRNATFPGVQMKFALQKLLNAVPEAIKGYKPVPVPARVPENKSCD
PATPLKQEWMWNQVSKFLQEGDVVITETGTSAFGINQTPFPNNAYGISQVLWGSIGFTTG
ACLGAAFAAEEIDPKKRVILFIGDGSLQLTVQEISTMIRWGLKPYLFVLNNDGYTIERLI
HGEKAGYNDIQNWDHLALLPTFGAKDYENHRVATTGEWDKLTQDKEFNKNSKIRMIEVML
PVMDAPTSLIEQAKLTASINAKQE

## back segment important
>sp|Q9HWK6|LYSC_PSEAE Lysyl endopeptidase OS=Pseudomonas aeruginosa (strain ATCC 15692 / DSM 22644 / CIP 104116 / JCM 14847 / LMG 12228 / 1C / PRS 101 / PAO1) OX=208964 GN=prpL PE=1 SV=1
MHKRTYLNACLVLALAAGASQALAAPGASEMAGDVAVLQASPASTGHARFANPNAAISAA
GIHFAAPPARRVARAAPLAPKPGTPLQVGVGLKTATPEIDLTTLEWIDTPDGRHTARFPI
SAAGAASLRAAIRLETHSGSLPDDVLLHFAGAGKEIFEASGKDLSVNRPYWSPVIEGDTL
TVELVLPANLQPGDLRLSVPQVSYFADSLYKAGYRDGFGASGSCEVDAVCATQSGTRAYD
NATAAVAKMVFTSSADGGSYICTGTLLNNGNSPKRQLFWSAAHCIEDQATAATLQTIWFY
NTTQCYGDASTINQSVTVLTGGANILHRDAKRDTLLLELKRTPPAGVFYQGWSATPIANG
SLGHDIHHPRGDAKKYSQGNVSAVGVTYDGHTALTRVDWPSAVVEGGSSGSGLLTVAGDG
SYQLRGGLYGGPSYCGAPTSQRNDYFSDFSGVYSQISRYFAP
