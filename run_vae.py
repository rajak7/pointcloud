import torch
import numpy as np
from args import get_args
from models.vae import VAE
from models.networks import Encoder, MLP_Decoder, autoregressive_decoder, TransformerEncoder

from utils import set_random_seed
from train import train
from test  import viz_reconstruct, sample_structure, eval_model_reconstruct ,eval_model_random_sample,cal_nelbo_samples

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

args = get_args()

args.zdim = 128
args.lr = 2e-3
args.tr_max_sample_points = 2048
args.data_dir="data/ShapeNetCore.v2.PC15k"
args.loss_sum_mean = "mean" # can be also "mean"

#args.random_rotate = True
#args.train_model = 1       #args.train_model=0 for evaluaton

set_random_seed(args.seed)

print("epochs log_freq  random_rotate",args.epochs,args.log_freq,args.random_rotate)

if args.encoder == 'transformer':
	encoder = TransformerEncoder
elif args.encoder == 'mlp':
	encoder = Encoder
else:
	raise Exception('Invalid encoder type:{0}'.format(args.encoder))

if args.deco_type == 'mlp':
   decoder = MLP_Decoder
   loss_type = 'chamfer'
elif args.deco_type == 'auto':
   decoder = autoregressive_decoder
   args.sort_input = True
   loss_type='auto_chamfer'
   print("Input is sorred:",args.sort_input,"along ",args.sort_dim,"into: ",args.n_groups)
else:
   raise Exception('Invalid decoder type:{0}'.format(args.deco_type))
	
model = VAE(encoder,decoder,args,loss_type)
 

if device.type == 'cuda':
    model = model.cuda()

#train model
if args.train_model == 1:
   train(model,args)

#evaliuate a trained model
if args.train_model == 0:
    args.resume_checkpoint='checkpoints/'+args.log_name+'/checkpoint-latest.pt'

    print("Resume Path:%s" % args.resume_checkpoint)
    checkpoint = torch.load(args.resume_checkpoint)
    model.load_state_dict(checkpoint['model'],strict=True)
    model.eval()
    #Generate random samples and reconstruct input and likelihood of the model computed on test data
    print("===========================================")
    print("Generate random samples and reconstruct input and likelihood of the model computed on test data")
    cal_nelbo_samples(model,args)
    viz_reconstruct(model,args)
    print("===========================================")
    print("Evaluation to the model on generated distribtuon of reconstruced data with denormalize = True ")
    eval_model_reconstruct(model,args,denormalize = True)
    print("===========================================")
    print("Evaluation to the model on generated distribtuon of reconstruced data with denormalize = False")
    eval_model_reconstruct(model,args,denormalize = False)
    if args.use_deterministic_encoder==False:
        sample_structure(model)
        print("===========================================")
        print("Model evaluation for random sample generation with denormalize = True")
        eval_model_random_sample(model,args,Nsamples=None,denormalize = True)
        print("===========================================")
        print("Model evaluation for random sample generation with denormalize = False")
        eval_model_random_sample(model,args,Nsamples=None,denormalize = False)
        
