import brownie
from web3 import Web3
import time
from brownie import Contract as bContract
from brownie import accounts as bAccount
from utils.liquidation_price import LiquidationPrice
import json

class BrownieInteractions(LiquidationPrice):
    
    def __init__(self,conf,network):        
        super().__init__(conf=conf,network=network)
        self.connect_brownie()
                            
    def reset_state(self):
        brownie.chain.revert()
                                
    def setup_brownie_contracts(self):

        self.brownieContracts = {}                                                                    
        contract = self.fetch_contract_from_resolver("PerpsV2MarketSettings")
        self.brownieContracts['perp_settings'] = bContract.from_abi(name='perp_settings', 
                                                                    address=contract.address, 
                                                                    abi=contract.abi)
        contract = self.fetch_contract_from_resolver("PerpsV2MarketData")
        self.brownieContracts['perps_data'] = bContract.from_abi(name='perp_data', 
                                                                 address=contract.address, 
                                                                 abi=contract.abi)
        
        contract = self.fetch_contract_from_resolver("ExchangeRates")
        self.brownieContracts['exchange_rates'] = bContract.from_abi(name='exchange_rates', 
                                                                     address=contract.address, 
                                                                     abi=contract.abi)        

        contract = self.fetch_contract_from_resolver("ProxysUSD")
        self.brownieContracts['susd'] = bContract.from_abi(name='susd', 
                                                           address=contract.address, 
                                                           abi=contract.abi)        
        
        contract = self.fetch_contract(address=self.conf["mock"][self.network])
        self.brownieContracts["mock"] = bContract.from_abi(name='mock', address=contract.address, abi=contract.abi)
        
    def set_oracle_to_mock(self,currencyKey):
        price          = self.brownieContracts["exchange_rates"].rateForCurrency(currencyKey)
        self.set_mock_price(newPrice=price, timestamp=time.time())
        return self.brownieContracts["exchange_rates"].addAggregator(currencyKey,self.brownieContracts["mock"].address,{'from':self.relayOwner})
    
    def get_susd(self,account,amount):        
        return self.brownieContracts['susd'].transfer(account,amount,{'from':self.susdWhale})

    def set_mock_price(self,newPrice,timestamp):
        return self.brownieContracts["mock"].setLatestAnswer(newPrice,timestamp,{'from':bAccount[0]})

    def reset_circuit_breaker(self,address):
        return self.contracts["breaker"].resetLastValue([address],[0],{'from':self.relayOwner})

    def set_perp_parameter(self,parameter,value,marketKey):        
        marketKeyHex  = self.w3.toHex(text=marketKey).ljust(66,"0")
        parameterName = 'set'+parameter[0].upper()+parameter[1:]
        fn            = getattr(self.brownieContracts['perp_settings'],parameterName)
        return fn(marketKeyHex,value,{'from':self.perpSettingsOwner})

    def get_perp_parameter(self,parameter,marketKey):       
        marketKeyHex  = self.w3.toHex(text=marketKey).ljust(66,"0")
        fn            = getattr(self.brownieContracts['perp_settings'],parameter)
        return fn.call(marketKeyHex  ,{'from':bAccount[-1]})
    
    def transfer_margin(self,ticker,account,amount):
        transferMarginAbi = '[{ "constant": false, "inputs": [ { "internalType": "int256", "name": "marginDelta", "type": "int256" } ], "name": "transferMargin", "outputs": [], "payable": false, "stateMutability": "nonpayable", "type": "function" }]'
        proxyAddress      = self.get_summary_value(ticker,"proxy_address")
        contract          = bContract.from_abi(name='market', address=proxyAddress, abi=json.loads(transferMarginAbi))
        return contract.transferMargin(amount,{'from':account})
    
    def set_atomic_fees_to_offchain_fees(self,ticker):
        marketKey = 's'+ticker.upper()+"PERP"
        for side in ['maker','taker']:
            atomicFee    = self.get_perp_parameter(f'{side}Fee',marketKey)
            offchainFee  = self.get_perp_parameter(f'{side}FeeOffchainDelayedOrder',marketKey )
            if atomicFee != offchainFee:
                self.set_perp_parameter(parameter=f'{side}Fee', value=offchainFee, marketKey=marketKey)
        

    def execute_atomic_order(self,ticker,account,amount):
        modifyPositionAbi = '[{ "constant": false, "inputs": [ { "internalType": "int256", "name": "sizeDelta", "type": "int256" }, { "internalType": "uint256", "name": "desiredFillPrice", "type": "uint256" } ], "name": "modifyPosition", "outputs": [], "payable": false, "stateMutability": "nonpayable", "type": "function" }]'
        proxyAddress      = self.get_summary_value(ticker,'proxy_address')
        contract          = bContract.from_abi(name='market', address=proxyAddress , abi=json.loads(modifyPositionAbi))
        limit             = int(1e30) if amount > 1 else 1
        return contract.modifyPosition(amount,limit,{'from':account})
    
    def get_perp_position(self,marketKey,accountAddress):
        marketKeyHex  = self.w3.toHex(text=marketKey).ljust(66,"0")
        position = self.brownieContracts['perps_data'].positionDetailsForMarketKey(marketKeyHex,accountAddress)
        labels = ['inner','notionalValue','profitLoss','accruedFunding','remainingMargin','accessibleMargin','liquidationPrice','canLiquidatePosition']
        position = {label: data for data, label in zip(position,labels)}
        labels = ['id','lastFundingIndex','margin','lastPrice','size']
        position.update({label: data for label, data in zip(labels,position["inner"])})
        del position["inner"]
        return position
    
    def v1_liquidation_check(self):
        contract = self.fetch_contract_from_resolver("FuturesMarketSettings")
        settingsContract = bContract.from_abi(name='futures_settings', address=contract.address, abi=contract.abi)        
        settingsContract.setLiquidationFeeRatio(3/1e4*1e18,{'from':self.relayOwner})
        contract = self.fetch_contract_from_resolver("FuturesMarketBNB")
        ethPositionContract = bContract.from_abi(name='futures_settings', address=contract.address, abi=contract.abi)        
        for liquidationBufferRation in range(25,100_000,100):
            settingsContract.setLiquidationBufferRatio(10000000000000000000000000000000*1e18,{'from':self.relayOwner})
            if ethPositionContract.canLiquidate('XXXXXXXXXXXXXXXXXXXXXXXXXXXXX'):
                print(liquidationBufferRation)
                break
    
    def brownie_revert(self):
        brownie.chain.revert()
    
    def connect_brownie(self):
        
        if brownie.network.is_connected():
            self.disconnect_brownie()

        #connect
        brownie.network.connect(self.conf["brownie"][self.network])
                                                
        #unlock the owner
        ownerAddress = self.resolver.functions.owner().call()
        bAccount.at(ownerAddress,force=True) 
        self.relayOwner = bAccount[-1]
        
        #unlock owner on perp settings
        contract = self.fetch_contract_from_resolver("PerpsV2MarketSettings")
        ownerAddress = contract.functions.owner().call()
        bAccount.at(ownerAddress,force=True) 
        self.perpSettingsOwner = bAccount[-1]
        
        #unlock the susd whale
        bAccount.at(self.conf["susdWhale"][self.network],force=True) 
        self.susdWhale = bAccount[-1]
        
        #setup the contracts
        self.setup_brownie_contracts()
            
        #update w3
        self.w3   = Web3(Web3.HTTPProvider(self.conf["nodes"]["brownie"]))
        
        #update all saved contracts to their brownie equivalent
        for contractAddress, contract in self.contracts.items():
            self.contracts[contractAddress] = self.w3.eth.contract(address=contractAddress,abi=contract.abi)
        
        #take snapshot
        brownie.chain.snapshot()
        
    
    def disconnect_brownie(self):
        brownie.network.disconnect()

    # contract = self.brownieContracts['perps_data']
    # marketKeyHex  = self.w3.toHex(text='sARBPERP').ljust(66,"0")
    # contract.positionDetailsForMarketKey(marketKeyHex ,"0x1e48e9Db4Dc781dFACA3c22652169ea71a52b24A",block_identifier=97156091)
    
#%%
if __name__ == '__main__':
    from utils.utility import parse_yaml
    conf = parse_yaml(r"config/conf.yaml")    
    self = BrownieInteractions(conf=conf, network='mainnet')
