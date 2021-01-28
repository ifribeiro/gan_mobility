
# -*- coding: utf-8 -*-
"""waze_gan_v01

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1e4dUOfobyO9yfcHqMpVlazYEwjkZ2JbD
"""

# from google.colab import drive

# drive.mount('/gdrive')


# utils
from datetime import datetime
from pickle import NONE
import sys
# numpy
import numpy as np
# tensorflow
from keras.layers import (Layer)
from keras.models import Sequential
# keras
from keras.optimizers import Adam
from numpy import load, ones, zeros

import discriminators as discs
import generators as gens
from utils import (convert_data, generate_fake_samples, generate_fake_samples3, generate_latent_points,
                  generate_latent_points3,get_slot_range, plot_training,save_training,get_real_samples, get_real_samples3,
                  plot_img)

np.random.seed(0)

base_url  = '/gdrive/My Drive/Colab Notebooks/Machine Learning/WAZE/'
path_v2 = "/gdrive/My Drive/Colab Notebooks/Machine Learning/WAZE/plots/discriminator_model/v2"
path_gan = "/gdrive/My Drive/Colab Notebooks/Machine Learning/WAZE/plots/gan_model/"

base_url_local = "/home/iran/Downloads/ds_waze/"


"""## Hstack layer"""

"""## Generator

### V2
"""

"""## Discriminator"""

def sample(n_ruas,n_weeks,n_slots):
  arrays = []
  for s in range(n_slots):
    for _ in range(n_ruas):
      ruas  = np.zeros(n_ruas)
      ix_ruas = np.random.randint(0,n_ruas)
      ruas[ix_ruas] = 1

      weeks = zeros(n_weeks)
      ix_weeks = np.random.randint(0,n_weeks)
      weeks[ix_weeks] = 1

      slots = zeros(n_slots)
      ix_slot = np.random.randint(0,n_slots)
      slots[ix_slot] = 1

      # carro = np.random.randn(1)
      carro = np.random.uniform(size=1)
      x = np.concatenate((ruas,weeks,slots, carro))
      arrays.append(x)
  
  return np.array(arrays)

def get_fake_samples(n_samples,n_streets=1,n_weeks=7,n_slots=25):

  array_samples = np.array([sample(n_streets,n_weeks,n_slots) for _ in range(n_samples)])
  X = np.array([np.hstack(arr.reshape(arr.shape[0],arr.shape[1],1)) for arr in array_samples])
  y = zeros((n_samples,1))

  return X,y

def hstack_data(dataset):
  """
  Horizontally stack the arrays in the dataset
  """

  convertido = []
  for arr in dataset:
    data0 = np.concatenate((arr.reshape(arr.shape[0],arr.shape[1],1)),axis=1)
    convertido.append(data0)
  return np.array(convertido)


def get_real_samples_week(nsamples, dataset, encoderWeekDay, wkday=0):
  """
  Return nsample for the provided week
  """
  real_samples = []
  while(len(real_samples)<nsamples):
    r,_ = get_real_samples(nsamples*10,dataset)
    hstacked = hstack_data(r)
    for i, arr in enumerate(hstacked):
      equals = (arr[0][2:9] == encoderWeekDay.transform([[wkday]]))
      if(equals.all()):
        real_samples.append(r[i])
        if(len(real_samples)==nsamples): break
  y = np.ones((nsamples,1))
  return real_samples,y


"""### loading the data"""
# TODO: MOVE FUCTION TO PROPER FILE
def load_data(filename=None,base_url=None):
  """
  Loads a saved file
  ----
  Params:
  - filename
  - base_url: path where the file is saved
  """
  print ("Loading file {}...".format(filename))
  try:
    # TODO: FIX URL IN LOAD
    data = load(filename)
  except FileNotFoundError as fnf:
    #print ("File {} not found.".format(filename))
    print ("File not found error: {0}".format(fnf))
    return None
  print ("Done.")
  return data

def preprocessing(data=None,n_streets=2,interval=30, h_stack=False):
  """
  Reshapes the dataset based on the number of streets
  and interval
  ----
  Params: 
  - data: the dataset to be processed
  - n_streets:
  - interval:
  """
  slots_range = (len(get_slot_range(interval)))*n_streets
  n_samples = int(data.shape[0]/slots_range)
  new_shape = (n_samples,slots_range,data.shape[-1])
  print ("Reshaping to ({},{},{})...".format(new_shape[0],new_shape[1],new_shape[2]))
  data = data.reshape(new_shape)
  if h_stack:
    print ("Horizontally stacking arrays...")
    data = [np.hstack(arr.reshape(arr.shape[0],arr.shape[1],1)) for arr in data]
    print ("Converting to numpy array...")
    data = np.array(data)
  print ("Done.")
  return data

#data = preprocessing(data=data,n_streets=2,interval=30, h_stack=True)


"""Possíveis problemas para o treinamento do discriminator:

* Poucas classes de ruas e dias da semana (assim, eventualmente aparecem entradas falsas que o discriminador entende como verdadeiras)
* Ainda falta adicionar a feature slots
* a rede definida é muito simples (sem `dropout` e sem ajuste do `learning rate` do optimizer)
* Função de ativação utilizada
* Conferir a utilização do argumento `return_sequences`
* Testar com adição de uma CNN
* Verificar as opções do `train_on_batch`

---
Perguntas:
* Até que ponto é aceitável que o discriminador erre as previsões?
* Quão acertivo costuma ser os modelos de classificação feitos com LSTM?

---
Links:
* Sobre `accuracy` na classificação [Link](https://www.fharrell.com/post/class-damage/)
"""

def define_gan(g_model,d_model,lr=0.0001, b1=0.5):
  d_model.trainable = False
  model = Sequential()
  model.add(g_model)
  model.add(d_model)
  opt = Adam(lr=lr, beta_1=b1)
  model.compile(loss='binary_crossentropy', optimizer=opt)
  return model

def train(g_model,d_model, gan_model, dataset, n_epochs=20,n_batch=256, 
          n_steps=None,n_features=None,image_title="",n_teste=None,n_rep=1,print_sample=False,path=None,encStreets=None,encWeek=None,encSlots=None):
  bat_per_epoch = int(dataset.shape[0]/n_batch)
  half_batch = int(n_batch/2)
  today = datetime.today()
  # for plotting
  r = range(bat_per_epoch)
  print("Starting training...")
  losses = []
  for i in range(n_epochs):
    losses_disc = []
    losses_gene = []
    losses_temp = []
    g_loss = 0    
    for j in range(bat_per_epoch):
      X_real,y_real = get_real_samples_week(half_batch,dataset,encWeek, wkday=4)
      X_fake,y_fake = generate_fake_samples(g_model=g_model,n_samples=half_batch,
                                            n_steps=n_steps, n_features=n_features)
      X,y = np.vstack((X_real, X_fake)), np.vstack((y_real, y_fake))
      d_loss, _ = d_model.train_on_batch(X,y)
      g_loss_tmp = []
      for _ in range(n_rep):
        X_gan = generate_latent_points(n_batch,n_steps,n_features)
        y_gan = ones((n_batch,1))      
        g_loss = gan_model.train_on_batch(X_gan,y_gan)
        g_loss_tmp.append(g_loss)
      losses_disc.append(d_loss)
      losses_gene.append(np.mean(g_loss_tmp))
      # print (">{}, {}/{}, d={:.3f}, g={:.3f}".format(i+1,j+1,bat_per_epoch,d_loss,g_loss))  
      if ((j%10 == 0) and (j!=0)):
        print (">{}, {}/{}, d={:.4f}, g={:.4f}".format(i+1,j+1,bat_per_epoch,d_loss,g_loss))
    losses_temp.append(losses_disc)
    losses_temp.append(losses_gene)
    losses.append(losses_temp)
    plot_training(i,loss_d=losses_disc,loss_g=losses_gene,path=path,today=today,image_title=image_title, n_teste=n_teste)
    if print_sample:
      X_fake,_ = generate_fake_samples(g_model=g_model,n_samples=2, n_steps=n_steps, n_features=n_features)
      print(convert_data(X_fake[:1], encoderStreets=encStreets,encoderWeekDay=encWeek,encoderSlots=encSlots))
  return losses

def train2(g_model,d_model,gan_model,dataset, n_epochs=20,n_batch=256, 
          image_title="",print_sample=False, latent_dim=100):
  bat_per_epoch = int(dataset.shape[0]/n_batch)
  half_batch = int(n_batch/2)
  
  r = range(bat_per_epoch)
  print("Starting training...")
  losses = []
  for i in range(n_epochs):    
    for j in range(bat_per_epoch):
      X_real,y_real = get_real_samples3(half_batch,dataset,wkday=4)
      X_fake,y_fake = generate_fake_samples3(g_model=g_model,n_samples=half_batch,latent_dim=latent_dim)
      X,y = np.vstack((X_real, X_fake)), np.vstack((y_real, y_fake))
      d_loss, _ = d_model.train_on_batch(X,y)
            
      X_gan = generate_latent_points3(n_batch,latent_dim)
      y_gan = ones((n_batch,1))      
      g_loss = gan_model.train_on_batch(X_gan,y_gan)
      
      # print (">{}, {}/{}, d={:.3f}, g={:.3f}".format(i+1,j+1,bat_per_epoch,d_loss,g_loss))  
      if ((j%10 == 0) and (j!=0)):
        print (">{}, {}/{}, d={:.4f}, g={:.4f}".format(i+1,j+1,bat_per_epoch,d_loss,g_loss))  
    
    
    # plot_training(i,r,loss_d=losses_disc,loss_g=losses_gene,path=None,today=today,image_title=image_title, n_teste=n_teste)
    if print_sample:
      X_fake,_ = generate_fake_samples3(g_model,2,latent_dim)
      X_fake = X_fake.reshape(2,48,4)
      plot_img(X_fake[0])   
      
  return losses



"""## training GAN

Melhor modelo até agora (28/10):
- generator_v4
- Discrinator: n_hiddens=20
- Durante treino: n_batch = 303, GAN treinada 2 vezes a cada iteração

A difereça entre o loss do discriminator e do generator são grandes, mas o generator estava convergindo
"""
def test_parameters(data, gen_models=None,batches_sizes=[256,303],epochs=1,learning_rates=[],nrepetitions=1, path_to_save=""):
  """
  Evaluates the generators models over a list of parameters
  ----
  Params:
  gen_models: list of generator models
  batch_sizes: list of batches sizes
  epochs: number of epochs
  lerning_rates: list of learning rates
  nrepetitions: number of times the generator will be trained
  path_to_save: path where the training results will be saved
  """
  #gen_models = {'v2':g_v2, 'v4':g_v4, 'v5':g_v5, 'v6':g_v6, 'v7':g_v7, 'v8':g_v8, 'v9':g_v9, 'v11':g_v11}
  # bs = 606
  for genmod in gen_models:
    hist_training = {}
    for bs in batches_sizes:
      for lr in learning_rates:
        for nrep in nrepetitions:
          print ("bs:{} g:{} lr:{} nrep:{}".format(bs,genmod,lr,nrep))
          array_training = []
          for i in range(1):
            #d_model = discriminator_model_v2(n_hiddens=20, n_steps=59,n_features=98,lr=0.0001,b1=0.5)
            d_model = discs.discriminator_model_v3(n_hiddens=10, n_steps=59,n_features=98,lr=lr,b1=0.5)
            g = gen_models[genmod]
            gan_model = define_gan(g,d_model,lr=0.0001,b1=0.5)
            line  = "{}_{}_exec:{}".format(genmod,i,bs)
            losses = train(g,d_model,gan_model,data,n_epochs=epochs,n_batch=bs,n_steps=98,n_features=59,image_title=line,n_teste=0,n_rep=nrep)
            d_model.reset_states()        
            g.reset_states()
            gan_model.reset_states()
            
            array_training.append(losses)
          klr = 1
          if (lr==0000.2):
            klr = 2
          key = "{}_bs{}_lr{}_nr{}".format(genmod,bs,klr,nrep)
          hist_training.setdefault(key,[])
          hist_training[key].append(array_training)
    filename = "t_{}_{}eps_db_menor.json".format(genmod,epochs)
    save_training(path_to_save,hist_training,filename)


def test_parameters2(data, batches_sizes=[152,256],path=None,encoderStreets=None, encoderWeekDay=None, encoderSlots=None):
  for bs in batches_sizes:    
    array_training = []
    #d_model = discriminator_model_v2(n_hiddens=20, n_steps=59,n_features=98,lr=0.0001,b1=0.5)
    # g = gen_models[k]
    print ("Execução: {}".format(bs))
    d_model = discs.discriminator_model_v3(n_hiddens=10, n_steps=59,n_features=98,lr=0.0001,b1=0.5)
    g = gens.generator_model_v2(dmunits=[10,3,3], n_features=98)
    gan_model = define_gan(g,d_model,lr=0.0001,b1=0.5)
    line  = "exec:{}_".format(bs)
    losses = train(g,d_model,gan_model,data[:7154],n_epochs=50,n_batch=bs,n_steps=98,n_features=59,image_title=line,n_teste=0,
                  n_rep=1, print_sample=True,path=path,encStreets=encoderStreets,encWeek=encoderWeekDay,encSlots=encoderSlots)
    d_model.reset_states()        
    g.reset_states()
    gan_model.reset_states()


# TODO: REMOVE
# if __name__ == "__main__":
#   path_to_ds = sys.argv[1]
#   path_to_save = sys.argv[2]
#   if (path_to_ds==None):
#     print ("A database is needed for the training.")
#     quit()
#   if (path_to_save==None):
#     path_to_save="./trainings/"
#   data = load_data(filename=path_to_ds)

  

#   # g_v2 = gens.generator_model_v2(n_streets=2,n_weeks=7,interval=30,n_features=98)
#   # g_v3 = gens.generator_model_v3(n_features=98)
#   g_v4 = gens.generator_model_v4(n_features=98)
#   # g_v5 = gens.generator_model_v5(n_features=98)
#   # g_v6 = gens.generator_model_v6(n_features=98)
#   # g_v7 = gens.generator_model_v7(n_features=98)
#   # g_v8 = gens.generator_model_v8(n_features=98)
#   # g_v9 = gens.generator_model_v9(n_features=98)
#   # g_v10 = gens.generator_model_v10(n_features=98)
#   # g_v11 = gens.generator_model_v11(n_features=98)

#   gen_models = {'v4':g_v4}
#   batches_sizes = [128]
#   epochs = 1
#   learning_rates=[0.0001]
#   nrepetitions = [1]

#   print("dataset in: {}".format(path_to_ds))
#   print("save in: {}".format(path_to_save))

#   test_parameters(gen_models,batches_sizes,epochs,learning_rates,nrepetitions,path_to_save)



  