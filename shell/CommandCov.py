

import pandas as pd
from sqlalchemy import *
from datetime import datetime, timedelta
import numpy as np
from config import *
from db.factors import styleFactors, industryFactors
from db import database
from CommandMatrixAdjust import *
from optparse import OptionParser
from ipdb import set_trace

# payback and resid is calculated in CommandCal.py
industryFactors.sort()
 
# load factor return 
def factorReturn(sdate, edate):

    db = create_engine(uris['multi_factor'])
    sql = "select * from `barra_factor_return` where trade_date >= '" + sdate + "' and trade_date <='" + edate +"'"
    payback = pd.read_sql(sql, db)

    return payback

# load regression resid for every stock or some stocks
def regressionResid(sdate, edate, stocks = None):

    db = create_engine(uris['multi_factor'])
    meta = MetaData(bind = db)
    t = Table('barra_regression_resid', meta, autoload = True)
    columns = [
        t.c.trade_date,
        t.c.stock_id,
        t.c.resid,
    ]
    sql = select(columns)
    sql = sql.where(t.c.trade_date >= sdate)
    sql = sql.where(t.c.trade_date <= edate)
    if stocks != None:
        sql = sql.where(t.c.stock_id.in_(stocks))
    resid = pd.read_sql(sql, db)

    return resid

# load factor exposure of every stock or some stocks
def factorExposure(date, industryFactors, stocks = None):

    db = create_engine(uris['multi_factor'])
    meta = MetaData(bind = db)
    t = Table('factor_exposure_barra', meta, autoload = True)
    columns = [
        t.c.trade_date,
        t.c.stock_id,
        #t.c.country,
        t.c.volatility,
        t.c.dividend_yield,
        t.c.quality,
        t.c.momentum,
        t.c.short_term_reverse,
        t.c.value,
        t.c.linear_size,
        t.c.nonlinear_size,
        t.c.growth,
        t.c.liquidity,
        t.c.sentiment,
        t.c.industry, # need further treatment
        #t.c.weight, # need further treatment
    ]
    sql = select(columns)
    sql = sql.where(t.c.trade_date == date)
    if stocks != None:
        sql = sql.where(t.c.stock_id.in_(stocks))
    exposure = pd.read_sql(sql, db)

    w = exposure
    w['country'] = 1
    
    for industry in industryFactors:
        w[industry] = 0
    for i in range(len(w)):
        w['industry_'+str(w['industry'][i])][i] = 1
    
    w = w.drop('industry', axis = 1)

    return w

# calculate factor fluctuation ratio
def FactorFluctuation(factorReturn):
    
    flr = factorReturn.std()

    return flr

# calculate covariance matirx
def FactorCovariance(w, sigma, omiga):

    covarianceMatrix = np.dot(np.dot(w,sigma),w.T) + omiga

    return covarianceMatrix

# calculate stock fluctuation ratio
def stockFluctuation(stockResid):

    stockFlr = stockResid.std()

    return stockFlr

# save factor return fluctuation ratio into barra_fluctuation_ratio
def saveFlr(flr, date, sdate = None, edate = None):

    df = pd.DataFrame(columns = ['bf_date','bf_factor','bf_flr'])
    df['bf_factor'] = flr.index
    df['bf_flr'] = flr.values
    df['bf_date'] = date
    df.set_index(['bf_date','bf_factor'], inplace = True)

    db = create_engine(uris['multi_factor'])
    meta = MetaData(bind = db)
    t = Table('barra_factor_fluctuation_ratio', meta, autoload = True)
    columns = [
        t.c.bf_date,
        t.c.bf_factor,
        t.c.bf_flr,
    ]
    sql = select(columns)
    if sdate != None:
        sql = sql.where(t.c.bf_date >= sdate)
    if edate != None:
        sql = sql.where(t.c.bf_date <= edate)
    dfBase = pd.read_sql(sql, db)
    dfBase['bf_date'] = dfBase['bf_date'].map(lambda x: pd.Timestamp(x).strftime('%Y-%m-%d'))
    dfBase.set_index(['bf_date','bf_factor'], inplace = True)

    database.batch(db, t, df, dfBase, timestamp = False)

# save factor return fluctuation ratio into barra_fluctuation_ratio
def saveStockFlr(stockFlr, date, sdate = None, edate = None):

    df = pd.DataFrame(columns = ['br_date','br_stock_id','br_flr'])
    df['br_stock_id'] = stockFlr.index
    df['br_flr'] = stockFlr.values
    df['br_date'] = date
    df.set_index(['br_date','br_stock_id'], inplace = True)

    db = create_engine(uris['multi_factor'])
    meta = MetaData(bind = db)
    t = Table('barra_resid_fluctuation_ratio', meta, autoload = True)
    columns = [
        t.c.br_date,
        t.c.br_stock_id,
        t.c.br_flr,
    ]
    sql = select(columns)
    if sdate != None:
        sql = sql.where(t.c.br_date >= sdate)
    if edate != None:
        sql = sql.where(t.c.br_date <= edate)
    dfBase = pd.read_sql(sql, db)
    dfBase['br_date'] = dfBase['br_date'].map(lambda x: pd.Timestamp(x).strftime('%Y-%m-%d'))
    dfBase.set_index(['br_date','br_stock_id'], inplace = True)

    database.batch(db, t, df, dfBase, timestamp = False)


# save factor return covariance into barra_factor_covariance
def saveFactorCovariance(mat, names, date, sdate = None, edate = None):

    df = pd.DataFrame(columns = ['bf_date','bf_factor1','bf_factor2','bf_cov'])
    dfFactor1 = list()
    dfFactor2 = list()
    covij = list()
    i = 0
    for name1 in names:
        j = i
        for name2 in names[i:]:
            dfFactor1.append(name1)
            dfFactor2.append(name2)
            covij.append(mat[i,j])
            j += 1
        i += 1
    df['bf_factor1'] = dfFactor1
    df['bf_factor2'] = dfFactor2
    df['bf_cov'] = covij
    df['bf_date'] = date
    df['bf_date'] = df['bf_date'].map(lambda x: pd.Timestamp(x).strftime('%Y-%m-%d'))
    df.set_index(['bf_date','bf_factor1','bf_factor2'], inplace = True)
    
    db = create_engine(uris['multi_factor'])
    meta = MetaData(bind = db)
    t = Table('barra_factor_covariance', meta, autoload = True)
    columns = [
        t.c.bf_date,
        t.c.bf_factor1,
        t.c.bf_factor2,
        t.c.bf_cov,
    ]
    sql = select(columns)
    if sdate != None:
        sql = sql.where(t.c.bf_date >= sdate)
    if edate != None:
        sql = sql.where(t.c.bf_date <= edate)
    dfBase = pd.read_sql(sql, db)
    dfBase['bf_date'] = dfBase['bf_date'].map(lambda x: pd.Timestamp(x).strftime('%Y-%m-%d'))
    dfBase.set_index(['bf_date','bf_factor1','bf_factor2'], inplace = True)

    database.batch(db, t, df, dfBase, timestamp = False)

# save stock return covariance into barra_covariance
def saveStockCovariance(mat, names, date, sdate = None, edate = None):

    df = pd.DataFrame(columns = ['bc_date','bc_stock1','bc_stock2','bc_cov'])
    dfStock1 = list()
    dfStock2 = list()
    covij = list()
    i = 0
    for name1 in names:
        j = i
        for name2 in names[i:]:
            dfStock1.append(name1)
            dfStock2.append(name2)
            covij.append(mat[i,j])
            j += 1
        i += 1
    df['bc_stock1'] = dfStock1
    df['bc_stock2'] = dfStock2
    df['bc_cov'] = covij
    df['bc_date'] = date
    df['bc_date'] = df['bc_date'].map(lambda x: pd.Timestamp(x).strftime('%Y-%m-%d'))
    df.set_index(['bc_date','bc_stock1','bc_stock2'], inplace = True)

    db = create_engine(uris['multi_factor'])
    meta = MetaData(bind = db)
    t = Table('barra_covariance', meta, autoload = True)
    columns = [
        t.c.bc_date,
        t.c.bc_stock1,
        t.c.bc_stock2,
        t.c.bc_cov,
    ]
    sql = select(columns)
    if sdate != None:
        sql = sql.where(t.c.bc_date >= sdate)
    if edate != None:
        sql = sql.where(t.c.bc_date <= edate)
    dfBase = pd.read_sql(sql, db)
    dfBase['bc_date'] = dfBase['bc_date'].map(lambda x: pd.Timestamp(x).strftime('%Y-%m-%d'))
    dfBase.set_index(['bc_date','bc_stock1','bc_stock2'], inplace = True)

    database.batch(db, t, df, dfBase, timestamp = False)

# main function
def handle(sdate, edate, date):
    
    fr = factorReturn(sdate, edate)
    fr.set_index('trade_date', inplace = True)
    fr.sort_index(ascending = True, inplace = True)
    fr.sort_index(axis = 1, inplace = True)
    fr = fr.fillna(0)
    factorNames = list(fr.columns)
  
    flr = FactorFluctuation(fr)
    saveFlr(flr = flr, date = date)
    print('Factor return fluctucation saved! Check barra_factor_fluctucation_ratio to see more details.')

    resid = regressionResid(sdate, edate)
    stocks = set(resid['stock_id'])
    resid.sort_values(by = ['trade_date','stock_id'],ascending = True, inplace = True)
    resid.set_index(['trade_date','stock_id'], inplace = True)
    resid = resid.unstack()['resid'].fillna(0)
    stockIds = list(resid.columns)
   
    weight = factorExposure(date, industryFactors, stocks)
    weight.sort_values(by = ['trade_date','stock_id'],ascending = True, inplace = True)
    weight.set_index(['trade_date','stock_id'], inplace = True)
    weight.sort_index(axis = 1 , inplace = True)
    w = np.matrix(weight)
    
    fr = np.matrix(fr).T
    flr = np.matrix(flr).T
    # fr and flr should be in the same shape!
    sigma = np.cov(fr)
    # do some adjustment 
    # all input should be in form of matrix
    sigma = nothing(sigma)
    # exponent weighed adjustment
#    sigma = exponentWeight(fr, halfLifeStd = 252, halfLifeR = 84)
    # newey-west adjustment
#    sigma = neweyWest(sigma, fr, qStd = 5, qR = 2, halfLifeStd = 252, halfLifR = 84)
    # eigen adjustment
#    sigma = eigen(sigma, fr, M = 1000, alpha = 1.2)
    # fluctuation ratio adjustment
#    sigma = fluctuation(sigma, fr, flr)

    residFlr = stockFluctuation(resid)
    saveStockFlr(residFlr, date)
    print('Stock return resid fluctucation saved! Check barra_resid_fluctucation_ratio to see more details.')

    # do some adjustment on omiga
    # if do nothing
    omiga = np.diag(resid.apply(lambda x: x**2).mean())
    # all input should be in form of matrix
    resid = np.mat(resid).T
    residFlr = np.mat(residFlr).T
    # exponent weighed adjustment
#    omiga = exponentWeight(resid, halfLifeStd = 84, halfLifeR = 84)
    # newey-west adjustment
#    omiga = neweyWest(omiga, resid, qStd = 5, qR = 5, halfLifeStd = 84, halfLife = 84)
    # structure model adjustment
#    omiga = structure(omiga)
    # bayes adjustment
#    omiga = bayes(omiga)
    # fluctuation ratio adjustment
#    omiga = fluctuation(omiga, resid, residFlr)

    covarianceMatrix = FactorCovariance(w, sigma, omiga)
    
    saveFactorCovariance(sigma, factorNames, date)
    print('Factor return covariance saved! Check barra_factor_covariance to see more details.') 
    saveStockCovariance(covarianceMatrix, stockIds, date)  ##### slow #####
    print('Stock return covariance saved! Check barra_stock_covariance to see more details.')


if __name__ == '__main__':
    opt = OptionParser()
    endDate = pd.Timestamp(datetime.today()).strftime('%Y-%m-%d')
    startDate = str(int(endDate[0:4])-1)+'-01-01'
    defaultDate = pd.Timestamp(datetime.today() - timedelta(days = 1)).strftime('%Y-%m-%d')
    defaultDate = '2019-12-31'
    opt.add_option('-s','--sdate',help = 'start date', default = startDate)
    opt.add_option('-e','--edate',help = 'end date', default = endDate)
    opt.add_option('-d','--date', help = 'date', default = defaultDate)
    opt, arg = opt.parse_args()
    handle(opt.sdate, opt.edate, opt.date)

