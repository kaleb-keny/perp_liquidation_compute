from utils.brownie_interaction import BrownieInteractions
import json
import time
from brownie import accounts as bAccount
from brownie import Contract as bContract

class BrownieTests(BrownieInteractions):

    def __init__(self,conf,network):        
        super().__init__(conf=conf,network=network)
        
    def test_liquidation_price_existing_position(self):
        
        for direction in [-1,1]:

            self.reset_state()
            
            trader = bAccount[2]
            
            self.get_susd(trader,40_000e18)
            
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
                
        self.reset_state()
                        
        chainlinkPrice = self.fetch_chainlink_price(ticker)

        #get the exact liquidation price
        liquidationPriceDict = self.fetch_exact_liquidation_price(accountAddress=accountAddress,
                                                                  ticker=ticker,
                                                                  sizeDelta=1,
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
    
#%%
if __name__ == '__main__':
    from utils.utility import parse_yaml
    conf = parse_yaml(r"config/conf.yaml")    
    self = BrownieTests(conf=conf, network="mainnet")    
    # testingPositions = [["0x21d099fE94FF5075654e36d7CaF0FeFADaFe7446","eth"],["0x783F1477E908E5906D0f2F77ee5ca859BD83eA83","gbp"]]
    # for userAddress,ticker in testingPositions:
    #     self.liquidation_of_existing_account_testing(accountAddress=userAddress,ticker=ticker)