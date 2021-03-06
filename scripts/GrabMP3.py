# -*- coding: utf-8 -*-
"""
Created on Mon Apr 18 08:38:10 2016

@author: Crystal.Humphries

GrabMP3.py uses a list of RSS websites and
grabs the first 5 MP3s and places them into
the bucket s3://podcastrecommender
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import boto
import re
import os
import json
import imp
import numpy as np

path_to_dir = '/home/ubuntu/PodcastRecommender/'
loc = os.path.join(path_to_dir, "src/twitter_followers_list.py")

'''Obtain list of rss websites'''


class Grab_MP3S(object):
    
    def __init__(self):
        self.bucket = None
        self.df = None
        self.broken_links = []
        
    def connect_bucket(self, bucket_name):
        '''uses api key to connect to bucket name'''
        home = os.environ['HOME']
        awi_loc = os.path.join(home, '.api/AWS.api')
        awi = json.load(open(awi_loc))
    
        access_key = str(awi['AWS_ACCESS_KEY'])
        secret_access_key = str(awi['AWS_SECRET_ACCESS_KEY'])
    
        conn = boto.connect_s3(access_key, secret_access_key)
        self.bucket = conn.get_bucket(bucket_name, validate=False)

    def _folder_name(self, title):
        if re.search('|', title):
            title = title.split('|')[0].strip()
        folder = title.replace(' ', "_")
        return folder

    def _write_to_s3(self, filename, folder, bucket):
        loc = os.path.join(folder, filename)
        file_object = bucket.new_key(loc)
        file_object.set_contents_from_filename(filename, policy='public-read')

    def _trim_names(self):
        df = pd.read_csv("../data/Podcast_additional_info.csv", low_memory=False)
        tweets = imp.load_source('get_twitter_followers', loc)
        tweets = tweets.get_twitter_followers()
        tweets.get_overlapping_users()
        df_followers = tweets.trim_users()
        titles = df_followers.index
        has_followers = df.Title.isin(titles)
        self.df = df.loc[has_followers, :]
    
    def get_start_stop(self, quintile):
        nrows = self.df.shape[0]
        one_quintile = int(np.round((nrows)/5.0))
        end = quintile*one_quintile
        start = end - one_quintile
        self.df = self.df.iloc[start:end, :]

    def send_to_S3(self, quintile=None):
        if quintile is not None:
            self.get_start_stop(quintile)
        self._trim_names()
        for i, rl in enumerate(self.df.NormalizedUrl):
            title = self.df.Title.values[i]
            url = 'https://' + rl
            try:
                response = requests.get(url)
                soup = BeautifulSoup(response.content)
                list_rss = soup.findAll('media:content')
                self.connect_bucket('podcastrecommenderbucket')
                title = self.df.Title.values[i]
                folder = self._folder_name(title)

                n = 0
                files=[]
                for rss in list_rss:
                    mp3 = rss.get('url')
                    cmd = 'wget ' + mp3
                    os.system(cmd)
                    filename = os.path.basename(mp3)
                    if filename.split('.')[-1] != 'mp3':
                        continue
                    if os.path.exists(filename):
                        n += 1
                        self._write_to_s3(filename, folder, self.bucket)
                        files.append(filename)
                    else:
                        continue
                    if n == 5:
                        break
                cmd_rm = 'rm -rf' + ' '.join(files)
                os.system(cmd_rm)
            except:
                self.broken_links.append(title)
