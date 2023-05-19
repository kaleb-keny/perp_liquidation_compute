from utils.contracts import Contracts
import requests
import pandas as pd


class LiquidationPrice(Contracts):
    
    def __init__(self,conf,network):
        super().__init__(conf=conf,network=network)
        self.update_all_market_summaries()
   
    def fetch_post_trade_details(self,accountAddress,ticker,sizeDelta,pythPriceWithDecimals):
        postTradeDetailsAbi = '[{ "constant": true, "inputs": [ { "internalType": "int256", "name": "sizeDelta", "type": "int256" }, { "internalType": "uint256", "name": "tradePrice", "type": "uint256" }, { "internalType": "enum IPerpsV2MarketBaseTypes.OrderType", "name": "orderType", "type": "uint8" }, { "internalType": "address", "name": "sender", "type": "address" } ], "name": "postTradeDetails", "outputs": [ { "internalType": "uint256", "name": "margin", "type": "uint256" }, { "internalType": "int256", "name": "size", "type": "int256" }, { "internalType": "uint256", "name": "price", "type": "uint256" }, { "internalType": "uint256", "name": "liqPrice", "type": "uint256" }, { "internalType": "uint256", "name": "fee", "type": "uint256" }, { "internalType": "enum IPerpsV2MarketBaseTypes.Status", "name": "status", "type": "uint8" } ], "payable": false, "stateMutability": "view", "type": "function" }]'
        proxyAddress  = self.get_summary_value(ticker,'proxy_address')
        proxyContract = self.w3.eth.contract(address=proxyAddress,abi=postTradeDetailsAbi)
        outputs       = proxyContract.functions.postTradeDetails(sizeDelta,pythPriceWithDecimals,2,accountAddress).call()
        labels        = ['remainingMargin','size','lastPrice','liquidationPrice','fee','status']
        return {label: output for label, output in zip(labels,outputs)}
    
    def fetch_position(self,accountAddress,ticker):
        proxyAddress = self.get_summary_value(ticker,'proxy_address')
        positionData = self.brownieContracts["perps_data"].positionDetails(proxyAddress,accountAddress)
        labels       = ['inner','notionalValue','profitLoss','accruedFunding','remainingMargin','accessibleMargin','liquidationPrice','canLiquidate']
        position     = {label: data for data, label in zip(positionData,labels)}
        labels       = ['id','lastFundingIndex','margin','lastPrice','size']
        position.update({label: data for label, data in zip(labels,position["inner"])})
        del position["inner"]
        return position
                
    def fetch_exact_liquidation_price(self,accountAddress,ticker,sizeDelta,pythPriceWithDecimals=None):
        
        if not pythPriceWithDecimals :
            pythPriceWithDecimals = int(self.fetch_pyth_price(ticker)*1e18)
            
        if sizeDelta == 0:
            sizeDelta = 1 #1 wei inconsequential change
        
        position = self.fetch_post_trade_details(accountAddress=accountAddress,
                                                 ticker=ticker,
                                                 sizeDelta=sizeDelta,
                                                 pythPriceWithDecimals=pythPriceWithDecimals)

        if position["status"] != 0:
            print("position status is not zero!, liquidation price cannot be accurately computed")
        
        if position["size"] == 0:
            print("no position to check")
            return None
        
        parameters   = self.fetch_market_parmeters(ticker)        
        perpSettings = self.fetch_contract_from_resolver('PerpsV2MarketSettings')
        minKeeperFee = perpSettings.functions.keeperLiquidationFee().call()
        maxKeeperFee = perpSettings.functions.maxKeeperFee().call()
        liquidationFeeRatio = perpSettings.functions.liquidationFeeRatio().call()
                
        df = pd.DataFrame(data=range(-500,500,1), columns=['prices'])
        df["prices"] = (1 + df["prices"] / 1e4) * position["liquidationPrice"] / 1e18
        
        #start with margin        
        df["remaining_margin"] = position["remainingMargin"] / 1e18
        
        #P&L
        df["p_l"] = ((position["lastPrice"] / 1e18)- df["prices"]) * (position["size"] / 1e18)
                
        # remove keeper fees min then max
        df["keeper_fee"] = df["prices"].apply(lambda p: max(p * abs(position["size"] / 1e18) * (liquidationFeeRatio/1e18), (minKeeperFee/1e18)))
        df["keeper_fee"] = df["keeper_fee"].apply(lambda x: min(x, maxKeeperFee/1e18))
        
        # remove fee that goes to debt pool
        df["stakers_fee"] = df["prices"] * abs(position["size"]/1e18) * (parameters["liquidationBufferRatio"]/1e18)

        # fetch liquidation premium        
        df["liquidation_premium"] = (position["size"]/1e18)**2 / (parameters["skewScale"] / 1e18) * df["prices"] * (parameters["liquidationPremiumMultiplier"] / 1e18)

        # net out against remaining margin
        df["remaining_margin"] = df["remaining_margin"] - (df["liquidation_premium"] + df["keeper_fee"] + df["stakers_fee"] + df["p_l"]) 
        
        if all(df.remaining_margin>0) or all(df.remaining_margin<0):
            print("liquidation price too wide to be calculated accurately")
            liquidationPrice = position["liquidationPrice"]/1e18
            safePrice        = position["liquidationPrice"]/1e18                
        elif position["size"] > 0:
            liquidationPrice = min(df["prices"][df["remaining_margin"] <= 0].max(),
                                   position["liquidationPrice"]/1e18)
            safePrice        = max(df["prices"][df["remaining_margin"] > 0].min(),
                                   position["liquidationPrice"]/1e18)
        else:
            liquidationPrice = max(df["prices"][df["remaining_margin"] <= 0].min(),
                                   position["liquidationPrice"]/1e18)
            safePrice        = min(df["prices"][df["remaining_margin"] > 0].max(),
                                   position["liquidationPrice"]/1e18)
        return {'liquidationPrice':liquidationPrice,'safePrice':safePrice}
            
    def fetch_market_parmeters(self,ticker):
        perpSettings = self.fetch_contract_from_resolver('PerpsV2MarketSettings')
        outputs = perpSettings.functions.parameters(self.w3.toHex(text='s'+ticker.upper()+"PERP")).call()
        labels  = ['takerFee','makerFee','takerFeeDelayedOrder','makerFeeDelayedOrder','takerFeeOffchainDelayedOrder','makerFeeOffchainDelayedOrder',
                   'maxLeverage','maxMarketValue','maxFundingVelocity','skewScale','nextPriceConfirmationWindow','delayedOrderConfirmationWindow',
                   'minDelayTimeDelta','maxDelayTimeDelta','offchainDelayedOrderMinAge','offchainDelayedOrderMaxAge','offchainMarketKey',
                   'offchainPriceDivergence','liquidationPremiumMultiplier','liquidationBufferRatio','maxLiquidationDelta','maxPD']
        
        return {k:v for k,v in zip(labels,outputs)}
                    
    
    def fetch_pyth_price(self,ticker):
        baseAsset         = self.get_summary_value(ticker,'baseAsset')
        perpsExchangeRate = self.fetch_contract_from_resolver('PerpsV2ExchangeRate')
        priceFeedId       = perpsExchangeRate.functions.offchainPriceFeedId(baseAsset).call()
        output = requests.get(self.conf["pyth"][self.network].format(self.w3.toHex(priceFeedId))).json()[0]
        return int(output["price"]["price"]) * 10 ** output["price"]["expo"]
    
    def fetch_chainlink_price(self,ticker):
        baseAsset         = self.get_summary_value(ticker,'baseAsset')
        contract = self.fetch_contract_from_resolver("ExchangeRates")
        return contract.functions.rateForCurrency(baseAsset).call()/1e18
            
    def update_all_market_summaries(self):
        marketDataContract = self.fetch_contract_from_resolver('PerpsV2MarketData')
        allSummaries       = marketDataContract.functions.allProxiedMarketSummaries().call()
        df                 = pd.DataFrame(allSummaries)
        df                 = pd.concat([df[df.columns[:-1]],df[df.columns[-1]].apply(pd.Series)],axis=1)
        df.columns         = ['proxy_address','baseAsset','marketKey','maxLeverage','price','marketSize','marketSkew','debt','currentFundingRate','currentFundingVelocity','takerFee','makerfee','takerFeeDelayedOrder','makerFeeDelayedOrder','takerFeeOffchainDelayedOrder','makerFeeOffchainDelayedOrder']
        df["ticker"]       = df["marketKey"].apply(self.w3.toText).str[1:].str.replace("\x00","").str.replace("PERP","").str.lower()
        self.marketSummariesDF = df
    
    def get_summary_value(self,ticker,description):
        return self.marketSummariesDF[self.marketSummariesDF["ticker"] == ticker][description].values[0]
    
#%%
if __name__ == '__main__':
    from utils.utility import parse_yaml
    conf = parse_yaml(r"config/conf.yaml")    
    self = LiquidationPrice(conf=conf,network='mainnet')