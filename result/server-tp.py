#!/usr/bin/env python

import sys
import os # OS stuff
import glob # pathname stuff
import csv # CSV
import re # Regex
from pprint import pprint # Pretty Print

import matplotlib.pyplot as plt
import matplotlib.cm as cmx
import matplotlib.colors as cl
from matplotlib import rcParams
from matplotlib.font_manager import FontProperties 

import pandas as pd
import numpy as np

def color_maker(count, map='gnuplot2', min=0.300, max=0.900):
  assert(min >= 0.000 and max <= 1.000 and max > min)
  gran = 100000.0
  maker = cmx.ScalarMappable(norm=cl.Normalize(vmin=0, vmax=int(gran)),
                             cmap=plt.get_cmap(map))
  r = [min * gran]
  if count > 1:
    r = [min * gran + gran * x * (max - min) / float(count - 1) for x in range(0, count)]
  return [maker.to_rgba(t) for t in r]

fname = "server-tp.csv"
nets = ['wifi', 'lte', '3g']
cpu_pers = [100,70,30,0]

with open(fname, 'rb') as f:
  data = csv.DictReader(f, delimiter=",")
  for row in data:
    if row['method'] == 'sq':
      sq_tp = float(row['scaledQPS']) 

baseline = [1.0] * len(nets)
tps = []

for cpu in cpu_pers:
  gpu = 100-cpu
  cur_tp = []
  for net in nets:
    with open(fname, 'rb') as f:
      data = csv.DictReader(f, delimiter=",")
      for row in data:
        if row['network'] == net and row['cpu%'] == str(cpu) and row['gpu%'] == str(gpu) and row['method'] == 'ns':
          cur_tp.append(float(row['scaledQPS']))

  tps.append(cur_tp)
          
rel_tps = []
for tp in tps:
  rel_tps.append([t/sq_tp for t in tp])

# plot
import matplotlib
from matplotlib import pyplot as plt

plt.rc("font", family="serif")
plt.rc("font", size=15)
plt.rc('legend',fontsize=15)

fig,ax1 = plt.subplots()
fig.set_size_inches(10, 5)
barwidth = 0.15
x_values = np.arange(len(nets))

colors = color_maker(1+len(rel_tps), map='afmhot')

# first baseline
ax1.bar(x_values, baseline, width=barwidth, color=colors[0], label="Baseline(Status-quo)")

# improvement
for idx,y in enumerate(rel_tps):
  print y 
  ax1.bar(x_values+barwidth+idx*barwidth, y, width=barwidth, color=colors[idx+1], label="%d%%CPU-%d%%GPU" % (cpu_pers[idx], 100-cpu_pers[idx]))   

xlabels = ['Wi-Fi', 'LTE', '3G']
ax1.set_xticks(x_values+2*barwidth)
ax1.set_xticklabels(xlabels)
ax1.set_xlim([-0.1, (len(xlabels)+2)*barwidth*len(cpu_pers)])

ax1.set_ylabel('Throughput Improvement (X)')
ax1.grid(axis='y')
legend1 = ax1.legend(loc='upper left')

import os
figname='server-tp'
plt.savefig(figname+'.eps', bbox_inches='tight')
os.popen('convert '+figname+'.eps ' + figname + '.jpg')
