from web3 import Web3
import time
import requests

class Contracts:
    
    def __init__(self,conf,network):
        self.conf         = conf
        self.contracts    = dict()
        self.network      = network
        self.w3           = Web3(Web3.HTTPProvider(conf["nodes"][self.network]))
        self.resolver     = self.fetch_contract(address=conf["resolver"][network])
        
    def fetch_abi(self,address):
        etherscanURL = self.conf["etherscan"][self.network]
        headers      = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
        url          = etherscanURL .format(address)
        while True:
            try:
                output = requests.get(url.format(address),headers=headers).json()
                if output["status"] == '1':
                    return output["result"]
            except Exception as e:
                print(f"etherscan error {e}, trying again")
                time.sleep(1)
    
    def fetch_contract(self,address):
        if address in self.contracts.keys():
            self.contracts[address].web3 = self.w3
            return self.contracts[address]
        abi  = self.fetch_abi(address=address)
        self.contracts[address] = self.w3.eth.contract(address=address,abi=abi)
        return self.contracts[address]
    
    def fetch_contract_from_resolver(self,contractName):
        address = self.resolver.functions.getAddress(self.w3.toHex(text=contractName)).call()
        return self.fetch_contract(address=address)

#%%
if __name__ == '__main__':
    from utils.utility import parse_yaml
    conf = parse_yaml(r"config/conf.yaml")    
    self = Contracts(conf=conf,network='mainnet')
    
    # #%%
    # account = '0x1e48e9Db4Dc781dFACA3c22652169ea71a52b24A'
    # ticker  = 'arb'
    # sizeDelta = int(1.111140741*1e24)
    # blockNumber = 97156089
    # pythPrice  = 1.1251
    # outputs       = proxyContract.functions.postTradeDetails(sizeDelta,int(pythPrice*1e18),2,account).call(block_identifier=blockNumber)
    # labels        = ['remainingMargin','size','lastPrice','estLiqPrice','fee','status']
    # postTradeDetails = {label: output for label, output in zip(labels,outputs)}
     
