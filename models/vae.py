import torch
from torch import nn
import torch.nn.functional as F
import utils as ut
import numpy as np
from metrics.evaluation_metrics import CD_loss
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
import pudb

class VAE(nn.Module):
    def __init__(self,encoder,decoder,args,loss_type='chamfer'):
        super(VAE, self).__init__()
        self.n_point = args.tr_max_sample_points
        self.point_dim = 3
        self.n_point_3 = self.point_dim * self.n_point 
        self.n_groups = args.n_groups
        self.g_points = int(self.n_point /self.n_groups)
        self.z_dim = args.zdim
        self.loss_type = loss_type
        self.loss_sum_mean = args.loss_sum_mean
        self.use_deterministic_encoder = args.use_deterministic_encoder
        self.use_encoding_in_decoder = args.use_encoding_in_decoder
        self.encoder = encoder(self.z_dim,self.point_dim,self.use_deterministic_encoder)
        
        if not self.use_deterministic_encoder and self.use_encoding_in_decoder:
            self.decoder = decoder(2 *self.z_dim,self.n_point,self.point_dim)
        elif args.deco_type == 'mlp':
            self.decoder = decoder(self.z_dim,self.n_point,self.point_dim)
        elif args.deco_type == 'auto':
            self.decoder = decoder(self.z_dim,self.n_point,self.point_dim,self.n_groups)
        else:
            raise Exception('Invalid decoder type:{0}'.format(args.deco_type))
           
        #set prior parameters of the vae model p(z)
        self.z_prior_m = torch.nn.Parameter(torch.zeros(1), requires_grad=False)
        self.z_prior_v = torch.nn.Parameter(torch.ones(1), requires_grad=False)
        self.z_prior = (self.z_prior_m, self.z_prior_v)
        self.type = 'VAE'
    
    def forward(self, inputs):
        x = inputs['x']
        m, v = self.encoder(x)
        if self.use_deterministic_encoder:
            y = self.decoder(m)
            kl_loss = torch.zeros(1)
        else:
            z =  ut.sample_gaussian(m,v)
            decoder_input = z if not self.use_encoding_in_decoder else \
            torch.cat((z,m),dim=-1) #BUGBUG: Ideally the encodings before passing to mu and sigma should be here.
            y = self.decoder(decoder_input)
            #compute KL divergence loss :
            p_m = self.z_prior[0].expand(m.size())
            p_v = self.z_prior[1].expand(v.size())
            kl_loss = ut.kl_normal(m,v,p_m,p_v)
        #compute reconstruction loss 
        if self.loss_type is 'chamfer':
            x_reconst = CD_loss(y,x)
        if self.loss_type is 'auto_chamfer':
            x_reconst=CD_loss(y[:,:self.g_points,:],x[:,:self.g_points,:])
            for i in range(1, self.n_groups):
                start_i=i*self.g_points
                end_i=(i+1)*self.g_points
                x_reconst = x_reconst + CD_loss(y[:,start_i:end_i,:],x[:,start_i:end_i,:])
        # mean or sum
        if self.loss_sum_mean == "mean":
            x_reconst = x_reconst.mean()
            kl_loss = kl_loss.mean()
        else:
            x_reconst = x_reconst.sum()
            kl_loss = kl_loss.sum()
        nelbo = x_reconst + kl_loss
        
        ret = {'nelbo':nelbo, 'kl_loss':kl_loss, 'x_reconst':x_reconst}
        return ret
    

    def sample_point(self,batch):
        p_m = self.z_prior[0].expand(batch,self.z_dim).to(device)
        p_v = self.z_prior[1].expand(batch,self.z_dim).to(device)
        z =  ut.sample_gaussian(p_m,p_v)
        decoder_input = z if not self.use_encoding_in_decoder else \
        torch.cat((z,p_m),dim=-1) #BUGBUG: Ideally the encodings before passing to mu and sigma should be here.
        y = self.decoder(decoder_input)
        return y

    def reconstruct_input(self,x):
        m, v = self.encoder(x)
        if self.use_deterministic_encoder:
            y = self.decoder(m)
        else:
            z =  ut.sample_gaussian(m,v)
            decoder_input = z if not self.use_encoding_in_decoder else \
            torch.cat((z,m),dim=-1) #BUGBUG: Ideally the encodings before passing to mu and sigma should be here.
            y = self.decoder(decoder_input)
        return y
