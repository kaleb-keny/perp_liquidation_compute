from utils.brownie_interaction import BrownieInteractions
import json
import time
import pandas as pd
from brownie import accounts as bAccount
from brownie import Contract as bContract

class BrownieTests(BrownieInteractions):

    def __init__(self,conf,network):        
        super().__init__(conf=conf,network=network)
        
    def test_liquidation_price_existing_position(self):
        
        for direction in [-1,1]:
            pass

            self.reset_state()
            
            trader = bAccount[2]
            
            self.get_susd(trader,40_000e18)
            
            #set size to something large
            self.set_perp_parameter(parameter='maxMarketValue', value=int(1e40), marketKey='sARBPERP')
            
            #deposit 40k$ into arb
            self.transfer_margin(ticker='arb', account=trader, amount=int(40_000e18))
            
            #get the chainlink price
            chainlinkPrice = self.fetch_chainlink_price('arb')
            
            size = direction * int(25*40e3/chainlinkPrice*1e18)
                    
            #set atomic fees to offchain fees
            self.set_atomic_fees_to_offchain_fees('arb')
            
            #open the position
            self.execute_atomic_order(ticker='arb',account=trader,amount=size)
                
            #get the estimated liquidation price from opening a 25x position
            liquidationPriceDict = self.fetch_exact_liquidation_price(accountAddress=trader.address,
                                                                      ticker='arb',
                                                                      sizeDelta=0,
                                                                      pythPriceWithDecimals=int(chainlinkPrice*1e18))
            #check if liquidation price is accurate
            self.liquidation_check(accountAddress=trader.address, 
                                   ticker='arb', 
                                   liquidationPriceDict=liquidationPriceDict)

    def test_liquidation_price_new_position(self):
        
        for direction in [-1,1]:

            self.reset_state()
            
            trader = bAccount[2]
            
            self.get_susd(trader,40_000e18)

            #set size to something larg
            self.set_perp_parameter(parameter='maxMarketValue', value=int(1e40), marketKey='sETHPERP')

            #set atomic fees to offchain fees
            self.set_atomic_fees_to_offchain_fees('eth')
    
            #set max keeper fee to 10k$ & liquidationFeeRatio to 35 bp
            self.brownieContracts['perp_settings'].setMaxKeeperFee(int(10_000*1e18),{'from':self.perpSettingsOwner})
            self.brownieContracts['perp_settings'].setLiquidationFeeRatio(int(35/1e4*1e18),{'from':self.perpSettingsOwner})
            
            #deposit 40k$ into eth
            self.transfer_margin(ticker='eth', account=trader, amount=int(40_000e18))
            
            #get the chainlink price
            chainlinkPrice = self.fetch_chainlink_price('eth')
            
            #50x leverage
            size = direction * int(50*40e3/chainlinkPrice*1e18)
                    
            #get the exact liquidation price from opening a 25x position
            liquidationPriceDict = self.fetch_exact_liquidation_price(accountAddress=trader.address,
                                                                      ticker='eth',
                                                                      sizeDelta=size,
                                                                      pythPriceWithDecimals=int(chainlinkPrice*1e18))
            #open the position
            self.execute_atomic_order(ticker='eth',account=trader,amount=size)
                    
            #check if exact liquidation price is accurate
            self.liquidation_check(accountAddress=trader.address, 
                                   ticker='eth', 
                                   liquidationPriceDict=liquidationPriceDict)

    def liquidation_of_existing_account_testing(self,accountAddress,ticker):
        
        #checks whether we can calculate a safe liquidation price on the accounts        
        self.reset_state()
                        
        chainlinkPrice = self.fetch_chainlink_price(ticker)
        
        #get the exact liquidation price
        liquidationPriceDict = self.fetch_exact_liquidation_price(accountAddress=accountAddress,
                                                                  ticker=ticker,
                                                                  sizeDelta=0,
                                                                  pythPriceWithDecimals=int(chainlinkPrice*1e18))
                
        #check if exact liquidation price is accurate
        if liquidationPriceDict:
            self.liquidation_check(accountAddress=accountAddress, 
                                   ticker=ticker, 
                                   liquidationPriceDict=liquidationPriceDict)
    
    def run_all_tests(self):
        fns = dir(self)
        for fn in fns:
            if fn[:5] == 'test_':
                print(f"runnning {fn}")
                run_test = getattr(self, fn)
                run_test()        
        
    def liquidation_check(self,accountAddress,ticker,liquidationPriceDict):
        canLiquidate  = self.can_liquidate(accountAddress=accountAddress, ticker=ticker, price=liquidationPriceDict["liquidationPrice"])        
        assert canLiquidate ,"liquidation price did not lead to liquidation"
        canLiquidate = self.can_liquidate(accountAddress=accountAddress, ticker=ticker, price=liquidationPriceDict["safePrice"])        
        assert not canLiquidate ,"safe price led to liquidation"
    
    def can_liquidate(self,accountAddress,ticker,price):
        
        #get the baseAsset
        baseAsset = self.get_summary_value(ticker=ticker, description='baseAsset')
        
        #set the mock oracle to base asset
        self.set_oracle_to_mock(baseAsset)
            
        #get proxy address
        proxyAddress    = self.get_summary_value(ticker=ticker, description='proxy_address')
        canLiquidateAbi = '''[{ "constant": true, "inputs": [ { "internalType": "address", "name": "account", "type": "address" } ], "name": "canLiquidate", "outputs": [ { "internalType": "bool", "name": "", "type": "bool" } ], "payable": false, "stateMutability": "view", "type": "function" }]'''
        contract        = bContract.from_abi(name='perp_proxy', address=proxyAddress    , abi=json.loads(canLiquidateAbi))
        
        self.set_mock_price(newPrice=price*1e18, timestamp=time.time())                
        return contract.canLiquidate(accountAddress)        
    
    
    def run_test_on_live_positions(self):
        #test whether the liquidation price is being computed
        #for positions mentions in positions.csv
        #note only positions with post trade details of status 0 are checked
        #the rest utilize the estimate liquidation price, which is accurate enough but not exact
        df = pd.read_csv(r"existing_positions/positions.csv")
        failedList = list()
        for idx, row in df.iterrows():
            ticker         = row.ticker
            accountAddress = row.account
            marketKey      = f's{ticker.upper()}PERP'
            self.set_perp_parameter(parameter='maxMarketValue', value=int(1e40), marketKey=marketKey)
            position = self.fetch_post_trade_details(accountAddress=accountAddress,
                                                     ticker=row.ticker,
                                                     sizeDelta=1,
                                                     pythPriceWithDecimals=int(self.fetch_chainlink_price(ticker=row.ticker)*1e18))
            if position['status'] == 0:
                try:
                    self.liquidation_of_existing_account_testing(accountAddress=accountAddress,ticker=row.ticker)
                except:
                    failedList.append({'ticker':ticker,'account':accountAddress})
            
        if len(failedList)>0:
            print("some failures were found!")
                
    
    
    def setup_instant_liquidation_position(self):
        
        #test whether positions with instant liquidation can be detected with the
        #exact liquidation price function        
        
        #trader
        trader = bAccount[1]
        
        margin = 1300*1e18
        
        #reset state
        self.reset_state()

        #fund an account with sUSD
        self.get_susd(trader,margin)

        #set size to something large
        self.set_perp_parameter(parameter='maxMarketValue', value=int(1e40), marketKey='sGMXPERP')
        
        #set fees to offchain
        self.set_atomic_fees_to_offchain_fees('gmx')
        
        #add margin
        self.transfer_margin(ticker='gmx', account=trader, amount=int(margin))
        
        #get max leverage 
        maxLeverage =  0.93 * self.get_perp_parameter('maxLeverage',"sGMXPERP")/1e18 
        
        #open position at max leverage that doesn't revert but gets immediately liquidatbale
        pythPrice = self.fetch_pyth_price('gmx')
        chainlinkPrice = self.fetch_chainlink_price('gmx')
        sizeDelta = int(maxLeverage * margin/ pythPrice)
        position = self.fetch_post_trade_details(accountAddress=trader.address, 
                                                 ticker='gmx', 
                                                 sizeDelta=sizeDelta , 
                                                 pythPriceWithDecimals=int(chainlinkPrice*1e18))        
        
        assert chainlinkPrice < position["liquidationPrice"]/1e18,"instant liquidation was not setup"

        liquidationPrice = self.fetch_exact_liquidation_price(trader.address,'gmx',sizeDelta,int(pythPrice*1e18))

        assert chainlinkPrice < liquidationPrice["safePrice"], "instant liquidation was properly detected"


#%%
if __name__ == '__main__':
    from utils.utility import parse_yaml
    conf = parse_yaml(r"config/conf.yaml")    
    self = BrownieTests(conf=conf, network="mainnet")    
    # self.run_all_tests()