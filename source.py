#!/usr/bin/env python
# coding: utf-8

# # {Project Title}📝
# 
# ![Banner](./assets/banner.jpeg)

# ## Topic
# *What problem are you (or your stakeholder) trying to address?*
# 📝 <!-- Answer Below -->
# I want to further understand what factors truly relate to the popularity of video games. Especailly with GTA 6 just around the corner, having garnered huge amounts of attention in every nook and crany of the internet before release. So im interested in what factors can affect a games popularity and whether or not things like reviews, price, and genre strongly influence that.

# ## Project Question
# *What specific question are you seeking to answer with this project?*
# *This is not the same as the questions you ask to limit the scope of the project.*
# 📝 <!-- Answer Below -->
# What factors are associated with the populartiy of video games and how can these factors help explain the popularity of GTA 6?

# ## What would an answer look like?
# *What is your hypothesized answer to your question?*
# 📝 <!-- Answer Below -->
# I think gmaes with higher player engagment strong review and certain genres to have generallly higher levels of popularity. I also expect games of established franchise to have higher popularity than less establised franchises. For GTA 6 comparing it to games of similar stature could lead to some promising results. The analysis would use charts such as scatter plots and bar charts, along with statistics such as correlations and median ownership.

# ## Data Sources
# *What 3 data sources have you identified for this project?*
# *How are you going to relate these datasets?*
# 📝 <!-- Answer Below -->
# Steam Games Dataset (games.csv) – Contains information about games including estimated owners, price, reviews, Metacritic scores, peak concurrent players, playtime, genres, and release dates.
# Backloggd Games Dataset (backloggd_games.csv) – Contains information about games including ratings, platforms, genres, plays, backlogs, wishlists, and reviews.
# Video Games Dataset (video_games.csv) – Contains information about games including different play styles, playtime, and console.

# ## Approach and Analysis
# *What is your approach to answering your project question?*
# *How will you use the identified data to answer your project question?*
# 📝 <!-- Start Discussing the project here; you can add as many code cells as you need -->

# In[13]:


# Start your code here
# Import the libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# In[14]:


# Load the datasets
steam = pd.read_csv("games.csv")
backloggd = pd.read_csv("backloggd_games.csv")
games = pd.read_csv("video_games.csv")


# In[16]:


# Display the first 5 rows
steam.head()


# In[17]:


# Display the first 5 rows
backloggd.head()


# In[18]:


# Display the first 5 rows
games.head()


# ## Resources and References
# *What resources and references have you used for this project?*
# 📝 <!-- Answer Below -->

# In[22]:


# ⚠️ Make sure you run this cell at the end of your notebook before every submission!
get_ipython().system('jupyter nbconvert --to python source.ipynb')

