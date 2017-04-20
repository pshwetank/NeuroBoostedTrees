#!/usr/bin/env python

'''
    File name: main_fig4.py
    Author: Guillaume Viejo
    Date created: 30/03/2017    
    Python Version: 2.7


'''

import warnings
import pandas as pd
import scipy.io
import numpy as np
# Should not import fonctions if already using tensorflow for something else
from fonctions import *
import sys, os
import itertools
import cPickle as pickle
import networkx as nx


#####################################################################
# DATA LOADING
#####################################################################
adrien_data = scipy.io.loadmat(os.path.expanduser('~/Dropbox (Peyrache Lab)/Peyrache Lab Team Folder/Data/HDCellData/data_test_boosted_tree.mat'))
# m1_imported = scipy.io.loadmat('/home/guillaume/spykesML/data/m1_stevenson_2011.mat')

#####################################################################
# DATA ENGINEERING
#####################################################################
data 			= 	pd.DataFrame()
data['time'] 	= 	np.arange(len(adrien_data['Ang']))		# TODO : import real time from matlab script
data['ang'] 	= 	adrien_data['Ang'].flatten() 			# angular direction of the animal head
data['x'] 		= 	adrien_data['X'].flatten() 				# x position of the animal 
data['y'] 		= 	adrien_data['Y'].flatten() 				# y position of the animal
data['vel'] 	= 	adrien_data['speed'].flatten() 			# velocity of the animal 
# Engineering features
data['cos']		= 	np.cos(adrien_data['Ang'].flatten())	# cosinus of angular direction
data['sin']		= 	np.sin(adrien_data['Ang'].flatten())	# sinus of angular direction
# Firing data
for i in xrange(adrien_data['Pos'].shape[1]): data['Pos'+'.'+str(i)] = adrien_data['Pos'][:,i]
for i in xrange(adrien_data['ADn'].shape[1]): data['ADn'+'.'+str(i)] = adrien_data['ADn'][:,i]



#######################################################################
# FONCTIONS DEFINITIONS
#######################################################################
def extract_tree_threshold(trees):
	n = len(trees.get_dump())
	thr = {}
	for t in xrange(n):
		gv = xgb.to_graphviz(trees, num_trees=t)
		body = gv.body		
		for i in xrange(len(body)):
			for l in body[i].split('"'):
				if 'f' in l and '<' in l:
					tmp = l.split("<")
					if thr.has_key(tmp[0]):
						thr[tmp[0]].append(float(tmp[1]))
					else:
						thr[tmp[0]] = [float(tmp[1])]					
	for k in thr.iterkeys():
		thr[k] = np.sort(np.array(thr[k]))
	return thr

def tuning_curve(x, f, nb_bins):	
	bins = np.linspace(x.min(), x.max()+1e-8, nb_bins+1)
	index = np.digitize(x, bins).flatten()    
	tcurve = np.array([np.mean(f[index == i]) for i in xrange(1, nb_bins+1)])  	
	x = bins[0:-1] + (bins[1]-bins[0])/2.
	return (x, tcurve)

def test_features(features, targets, learners = ['glm_pyglmnet', 'nn', 'xgb_run', 'ens']):
    '''
        Main function of the script
        Return : dictionnary with for each models the score PR2 and Yt_hat
    '''
    X = data[features].values
    Y = np.vstack(data[targets].values)
    Models = {method:{'PR2':[],'Yt_hat':[]} for method in learners}
    learners_ = list(learners)
    print learners_

    # Special case for glm_pyglmnet to go parallel
    if 'glm_pyglmnet' in learners:
        print('Running glm_pyglmnet...')                
        # # Map the targets for 6 cores by splitting Y in 6 parts
        pool = multiprocessing.Pool(processes = 6)
        value = pool.map(glm_parallel, itertools.izip(range(6), itertools.repeat(X), itertools.repeat(Y)))
        Models['glm_pyglmnet']['Yt_hat'] = np.vstack([value[i]['Yt_hat'] for i in xrange(6)]).transpose()
        Models['glm_pyglmnet']['PR2'] = np.vstack([value[i]['PR2'] for i in xrange(6)])     
        learners_.remove('glm_pyglmnet')        

    for i in xrange(Y.shape[1]):
        y = Y[:,i]
        # TODO : make sure that 'ens' is the last learner
        for method in learners_:
            if method != 'ens': # FIRST STAGE LEARNING          
                print('Running '+method+'...')                              
                Yt_hat, PR2 = fit_cv(X, y, algorithm = method, n_cv=8, verbose=1)       
                Models[method]['Yt_hat'].append(Yt_hat)
                Models[method]['PR2'].append(PR2)           

            elif method == 'ens': # SECOND STAGE LEARNING
                X_ens = np.transpose(np.array([Models[m]['Yt_hat'][i] for m in learners if m != method]))
                #We can use XGBoost as the 2nd-stage model
                Yt_hat, PR2 = fit_cv(X_ens, y, algorithm = 'xgb_run', n_cv=8, verbose=1)        
                Models['ens']['Yt_hat'].append(Yt_hat)      
                Models['ens']['PR2'].append(PR2)                        

    for m in Models.iterkeys():
        Models[m]['Yt_hat'] = np.array(Models[m]['Yt_hat'])
        Models[m]['PR2'] = np.array(Models[m]['PR2'])
        
    return Models


#####################################################################
# COMBINATIONS DEFINITION
#####################################################################
combination = {}
targets = [i for i in list(data) if i.split(".")[0] in ['Pos', 'ADn']]

for n in ['Pos', 'ADn']:			
	combination[n] = {'peer':{},'cros':{}}	
	sub = [i for i in list(data) if i.split(".")[0] == n]
	for k in sub:
		combination[n]['peer'][k] = {	'features'	: [i for i in sub if i != k],
										'targets'	: k
									}
		combination[n]['cros'][k] = { 	'features'	: [i for i in targets if i.split(".")[0] != k.split(".")[0]],
										'targets'	: k
									}

########################################################################
# MAIN LOOP FOR R2
########################################################################
methods = ['xgb_run', 'nn', 'lin_comb']
final_data = {}
# for g in combination.iterkeys():
# 	final_data[g] = {}
# 	for w in combination[g].iterkeys():
# 		final_data[g][w] = {}
# 		for k in combination[g][w].iterkeys():
# 		    features = combination[g][w][k]['features']
# 		    targets =  combination[g][w][k]['targets'] 
# 		    results = test_features(features, targets, methods)
# 		    final_data[g][w][k] = results

with open("../data/fig4.pickle", 'rb') as f:
	final_data = pickle.load(f)

#####################################################################
# LEARNING XGB
#####################################################################

# bsts = {}
# params = {'objective': "count:poisson", #for poisson output
#     'eval_metric': "logloss", #loglikelihood loss
#     'seed': 2925, #for reproducibility
#     'silent': 1,
#     'learning_rate': 0.05,
#     'min_child_weight': 2, 'n_estimators': 580,
#     'subsample': 0.6, 'max_depth': 5, 'gamma': 0.4}        
# num_round = 100

# for g in combination.iterkeys():
# 	bsts[g] = {}
# 	for w in combination[g].iterkeys():
# 		bsts[g][w] = {}
# 		for k in combination[g][w].iterkeys():
# 			features = combination[g][w][k]['features']
# 			targets =  combination[g][w][k]['targets']	
# 			X = data[features].values
# 			Yall = data[targets].values		
# 			dtrain = xgb.DMatrix(X, label=Yall)
# 			bst = xgb.train(params, dtrain, num_round)
# 			bsts[g][w][k] = bst

# #####################################################################
# # TUNING CURVE
# #####################################################################
# all_neurons = [i for i in list(data) if i.split(".")[0] in ['Pos', 'ADn']]
# X = data['ang'].values
# Yall = data[all_neurons].values
# tuningc = {all_neurons[i]:tuning_curve(X, Yall[:,i], nb_bins = 100) for i in xrange(Yall.shape[1])}


#####################################################################
# EXTRACT TREE STRUCTURE
#####################################################################
# thresholds = {}
# for g in combination.iterkeys():
# 	thresholds[g] = {}
# 	for w in combination[g].iterkeys():
# 		thresholds[g][w] = {}
# 		for k in combination[g][w].iterkeys():
# 			thresholds[g][w][k] = extract_tree_threshold(bsts[g][w][k])		

# # need to sort the features by the number of splits
# sorted_features = dict.fromkeys(thresholds)
# for k in sorted_features.iterkeys():
# 	count = np.array([len(thresholds[k][f]) for f in thresholds[k].iterkeys()])
# 	name = np.array([combination[k]['features'][int(i[1:])] for i in thresholds[k].iterkeys()])
# 	sorted_features[k] = [name[np.argsort(count)], np.sort(count)]

# # matrix relation of splits between neurons
# relation = {}
# for k in ['Pos', 'ADn']:
# 	keys = [i for i in thresholds.iterkeys() if i.split(".")[0] == k]
# 	tmp = np.zeros((len(keys), len(keys)))
# 	for l in keys:
# 		for m,n in zip(sorted_features[l][0], sorted_features[l][1]):
# 			i = int(l.split(".")[1])
# 			j = int(m.split(".")[1])
# 			tmp[i, j] = n
# 	relation[k] = tmp
# 	#let's normalize the matrix
# 	relation[k] = relation[k]/np.max(relation[k])

#####################################################################
# PLOTTING
#####################################################################
def figsize(scale):
    fig_width_pt = 483.69687                         # Get this from LaTeX using \the\textwidth
    inches_per_pt = 1.0/72.27                       # Convert pt to inch
    golden_mean = (np.sqrt(5.0)-1.0)/2.0            # Aesthetic ratio (you could change this)
    fig_width = fig_width_pt*inches_per_pt*scale    # width in inches
    fig_height = fig_width*golden_mean              # height in inches
    fig_size = [fig_width,fig_height]
    return fig_size

def simpleaxis(ax):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.get_xaxis().tick_bottom()
    ax.get_yaxis().tick_left()
    # ax.xaxis.set_tick_params(size=6)
    # ax.yaxis.set_tick_params(size=6)


import matplotlib as mpl

mpl.use("pdf")
pdf_with_latex = {                      # setup matplotlib to use latex for output
    "pgf.texsystem": "pdflatex",        # change this if using xetex or lautex
    "text.usetex": True,                # use LaTeX to write all text
    "font.family": "serif",
    "font.serif": [],                   # blank entries should cause plots to inherit fonts from the document
    "font.sans-serif": [],
    "font.monospace": [],
    "axes.labelsize": 10,               # LaTeX default is 10pt font.
    "font.size": 8,
    "legend.fontsize": 7,               # Make the legend/label fonts a little smaller
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "figure.figsize": figsize(1),     # default fig size of 0.9 textwidth
    "pgf.preamble": [
        r"\usepackage[utf8x]{inputenc}",    # use utf8 fonts becasue your computer can handle it :)
        r"\usepackage[T1]{fontenc}",        # plots will be generated using this preamble
        ],
    "lines.markeredgewidth" : 0.2,
    "axes.linewidth"        : 0.5,
    "ytick.major.size"      : 1.5,
    "xtick.major.size"      : 1.5
    }    
mpl.rcParams.update(pdf_with_latex)
import matplotlib.gridspec as gridspec
from matplotlib.pyplot import *


labels = {'mb_10':'MB \n 10 bins', 
            'mb_60':'MB \n 60 bins', 
            'mb_360':'MB \n 360 bins', 
            'lin_comb':'Lin', 
            'nn':'NN', 
            'xgb_run':'XGB'}

colors_ = {'ADn':'#134B64', 'Pos':'#F5A21E'}
labels_plot = [labels[m] for m in methods[0:-1]]

figure(figsize = figsize(0.5))

simpleaxis(gca())
y = []
err = []
x = [0.0]
color = []

for g in ['peer', 'cros']:
	for m in ['xgb_run', 'nn']:
		for k in ['ADn', 'Pos']:			
			PR2_art = []    		
			color.append(colors_[k])
			for n in final_data[k][g].iterkeys():
				PR2_art.append(final_data[k][g][n][m]['PR2'])
			y.append(np.mean(PR2_art))
			err.append(np.std(PR2_art)/np.sqrt(np.size(PR2_art)))
			x.append(x[-1]+0.42)
		x[-1] += 0.3
	x[-1] += 0.5
		
x = np.array(x)
y = np.array(y)
err = np.array(err)		
x_adn = x[0:-1][np.arange(0, len(y),2)]
y_adn = y[np.arange(0, len(y),2)]
e_adn = err[np.arange(0, len(y),2)]
x_pos = x[0:-1][np.arange(1, len(y),2)]
y_pos = y[np.arange(1, len(y),2)]
e_pos = err[np.arange(1, len(y),2)]

bar(x_adn, y_adn, 0.4, align='center',
            ecolor='k', color = colors_['ADn'], alpha=.9, ec='w', yerr=e_adn, label = 'Antero Dorsal nucleus')
bar(x_pos, y_pos, 0.4, align='center',
            ecolor='k', color = colors_['Pos'], alpha=.9, ec='w', yerr=e_pos, label = 'Post Subiculum')
            
plot(x[0:-1], y, 'k.', markersize=3)         

xlim(np.min(x)-0.5, np.max(x[0:-1])+0.5)
ylabel('Pseudo-R2')
xticks(x_adn+0.2, ['XGB', 'NN']*2)

legend(bbox_to_anchor=(0.5, 1.2), loc='upper center', ncol=2, frameon = False)

figtext(0.2, -0.2, "ADn $\Rightarrow$ ADn \n Post-S $\Rightarrow$ Post-S \n \scriptsize{(Features $\Rightarrow$ Target)}")
figtext(0.6, -0.14, "ADn $\Rightarrow$ Post-S \n Post-S $\Rightarrow$ ADn")

savefig("../../figures/fig4.pdf", dpi=900, bbox_inches = 'tight', facecolor = 'white')
os.system("evince ../../figures/fig4.pdf &")
