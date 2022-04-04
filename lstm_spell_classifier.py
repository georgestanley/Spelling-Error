import json

import random

import numpy

from nltk.corpus.reader import WordListCorpusReader
import numpy as np
from nltk.corpus import stopwords
from utils import *
import torch
from torch import nn
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from Model import MLPNetwork,RNN
import torch.optim as optim
import sys,random
from torch.utils.data import TensorDataset, DataLoader, Dataset
from utils import get_rand01

all_letters = string.ascii_letters + " .,;'"
n_letters = len(all_letters)
n_iters = 100000
print_every = 1000
plot_every = 1000
batchsize=100
alph = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,:;'*!?`$%&(){}[]-/\@_#"

num_epochs=5


class LSTMModel(nn.Module):
    def __init__(self, input_dim, hidden_dim, layer_dim, output_dim):
        super(LSTMModel, self).__init__()
        self.hidden_dim = hidden_dim

        # Number of hidden layers
        self.layer_dim = layer_dim

        # Building your LSTM
        # batch_first=True causes input/output tensors to be of shape
        # (batch_dim, seq_dim, feature_dim)
        self.lstm = nn.LSTM(input_dim, hidden_dim, layer_dim, batch_first=True)

        # Readout layer
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        # Initialize hidden state with zeros
        h0 = torch.zeros(self.layer_dim, x.size(0), self.hidden_dim).requires_grad_()

        # Initialize cell state
        c0 = torch.zeros(self.layer_dim, x.size(0), self.hidden_dim).requires_grad_()

        # 28 time steps
        # We need to detach as we are doing truncated backpropagation through time (BPTT)
        # If we don't, we'll backprop all the way to the start even after going through another batch
        out, (hn, cn) = self.lstm(x, (h0.detach(), c0.detach()))

        # Index hidden state of last time step
        # out.size() --> 100, 28, 100
        # out[:, -1, :] --> 100, 100 --> just want last time step hidden states!
        out = self.fc(out[:, -1, :])
        # out.size() --> 100, 10
        return out

def insert_errors(data):

    temp=[]
    for x in data[:, 0]:
        if get_rand01() == 1:
            yy = np.array2string(x).replace("'", "")
            rep_char = int2char(np.random.randint(0, 26))
            rep_pos = np.random.randint(low=0, high=len(yy))
            temp.append(yy[0:rep_pos] + rep_char + yy[rep_pos + 1:])
    x2=np.ones((len(temp)))
    x = np.column_stack((temp,x2))
    data = np.concatenate((data,x))
    return data


def binarize (token,label, alph):

    bin_beg =  [0] * len(alph)
    bin_middle = [0] * len(alph)
    bin_end = [0] * len(alph)

    bin_beg[alph.index(token[0])] += 1
    bin_end[alph.index(token[-1])] += 1

    for i in range(1,len(token)-1):
        bin_middle[alph.index(token[i])] += 1

    bin_all = bin_beg + bin_middle + bin_end
    return torch.tensor(bin_all), torch.tensor(int(float(label))), token

def vectorize_data(data_arr):
    # https://arxiv.org/pdf/1608.02214.pdf

    data_arr = np.column_stack((data_arr[0],data_arr[1]))
    data_arr =insert_errors(data_arr)
    #X_vec = torch.zeros((int(len(data_arr) / batchsize), batchsize, len(alph) * 3))
    X_vec = torch.zeros((len(data_arr), len(alph) * 3))
    Y_vec = torch.zeros((len(data_arr), 1))
    X_token = []
    #TODO:
    #make X_token as np.array so that it can contain strings
    #shuflle it same way as for tensor ... X_token = X_token[r]

    for m, mini_batch_tokens in enumerate(zip(*[iter(data_arr)])):
        X_token_m = []
        x_mini_batch = torch.zeros((1, len(alph) * 3)) # (1,228)
        y_mini_batch = torch.zeros((1, 1)) #(1,1)


        for j, token in enumerate(mini_batch_tokens):
            x,y,z= binarize(token[0],token[1],alph)
            x_mini_batch, y_mini_batch, x_token = x,y,z
            '''
            if jumble_type == 'NO':
                x_mini_batch[j], x_token = binarize.noise_char(token, noise_type, alph)
            else:
                x_mini_batch[j], x_token = binarize.jumble_char(token, jumble_type, alph)
            '''

            #bin_label = [0] * len(vocab)
            #bin_label[vocab[token]] = 1
            #y_mini_batch[j] = np.array(bin_label)
            X_token_m.append(x_token)
        X_vec[m] = x_mini_batch
        Y_vec[m] = y_mini_batch
        X_token.append(X_token_m)

        percentage = int(m * 100. / (len(data_arr) / batchsize))
        #sys.stdout.write("\r%d %% %s" % (percentage, 'train data'))
        # print(str(percentage) + '%'),
        sys.stdout.flush()

    #print(X_vec.shape,Y_vec.shape)

    r = torch.randperm(X_vec.size()[0])
    X_vec = X_vec[r]
    Y_vec = Y_vec[r]

    return X_vec ,Y_vec,X_token

def get_wikipedia_words(file_name):

    with open(file_name) as f:
        data = f.read()
        words = json.loads(data)
    return words

def convert_to_numpy(words):

    non_ascii_keys = []
    for x in words.keys():
        if x.isascii()!= True:
            non_ascii_keys.append(x)
    for x in non_ascii_keys:
        del words[x]

    x1 = np.array(list(words.keys()))
    x2 = np.zeros( x1.size)
    x = np.column_stack((x1,x2))
    return (x1, x2)

class MyDataset(torch.utils.data.Dataset):

    def __init__(self, words, labels):
        self.words = words
        self.labels = labels

    def __getitem__(self, i):
        word = self.words[i]
        label = int(self.labels[i])
        return (word, label)

    def __len__(self):
        return len(self.labels)


def convert_to_pytorch_dataset(data):
    '''

    :param data: tuple (2)
    words : ndarray (9990,)
    labels: ndarray (9990,)
    :return:
    '''
    words = data[0]
    labels = data[1]

    #word_tensor = torch.Tensor(words)
    #labels = torch.Tensor(labels)

    my_dataset= MyDataset(words, labels)
    my_dataloader = DataLoader(my_dataset, batch_size=200, shuffle=True)

    val_dataset = MyDataset(words, labels)
    val_dataloader = DataLoader(val_dataset, batch_size=500, shuffle=False)

    return my_dataloader, val_dataloader

def test_dataloader(my_dataloader):

    for i , (word, label) in enumerate(my_dataloader):
        print(i, word , label)
        return

def initialize_model(n_hidden_layers):

    input_dim = 228
    hidden_dim = 100
    layer_dim = n_hidden_layers
    output_dim = 2

    model = LSTMModel(input_dim, hidden_dim, layer_dim, output_dim)

    learning_rate = 0.01
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.CrossEntropyLoss()

    return model, criterion, optimizer

def train_model(train_loader,val_loader, model,criterion, optim ):

    iter = 0
    n_epoch=30
    for epoch in range(n_epoch):
        for i, data  in enumerate(train_loader):
            X_vec, Y_vec, X_token = vectorize_data(data) # xx shape:
            X_vec = torch.unsqueeze(X_vec,1).requires_grad_() # (n_words,228) --> (n_words , 1, 228)
            Y_vec = torch.squeeze(Y_vec).type(torch.LongTensor)
            optim.zero_grad()
            # Forward pass to get output/logits
            # outputs.size() --> 100, 10
            outputs = model(X_vec)  # (n_words, 2)#

            # Calculate Loss: softmax --> cross entropy loss
            loss = criterion(outputs, Y_vec)

            # Getting gradients w.r.t. parameters
            loss.backward()

            # Updating parameters
            optim.step()

            #print(loss.item())

        #validation
        #TODO: Improve this validation section
        correct = 0
        total = 0

        for i, data in enumerate(val_loader):
            X_vec, Y_vec, X_token = vectorize_data(data)  # xx shape:
            X_vec = torch.unsqueeze(X_vec, 1).requires_grad_()  # (n_words,228) --> (n_words , 1, 228)
            Y_vec = torch.squeeze(Y_vec).type(torch.LongTensor)
            #print(X_token)
            # Forward pass to get output/logits
            # outputs.size() --> 100, 10
            outputs = model(X_vec)  # (n_words, 2)#

            # Get predictions from the maximum value
            _, predicted = torch.max(outputs.data, 1)

            # Total number of labels
            total += Y_vec.size(0)

            # Total correct predictions
            correct += (predicted == Y_vec).sum()

            #check for an index
            #print(f" Word = {X_token[60]} Prediction= {predicted[60]}")

            break

        accuracy = 100 * correct / total

        print(f" Word = {X_token[600]} Prediction= {predicted[600]} loss = {loss.item()} accuracy= {accuracy}")

    return

def main():

    model_type='RNN'
    n_letters = len(all_letters)
    n_classes = 2
    data = get_wikipedia_words('D:\\Freiburg\\MasterProject\\top_30000_words_over_200000.json')
    data = convert_to_numpy(data)
    train_loader, val_loader = convert_to_pytorch_dataset(data)
    #test_dataloader(dataloader)
    model, criterion, optim = initialize_model(n_hidden_layers=1)
    train_model(train_loader, val_loader, model, criterion, optim)

    return
    data_arr = insert_errors(data_arr)
    np.random.shuffle(data_arr)
    print(data_arr.shape)



    return

if __name__=="__main__":
    print("LSTM Spelling Classifier")
    main()