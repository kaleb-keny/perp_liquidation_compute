# Synthetix Perp Liquidation Price Calculation
 Calculates an accurate liquidation price for synthetix Perps V2 Positions

## To Setup
### CREATE FOLDER FOR A PROJECT
```
mkdir liquidation
cd liquidation
git clone git@github.com:Synthetixio/perp_liquidation_compute.git liquidation
```

### Add Config File
- create folder config under project director
- create file conf.yaml that includes the below information

```
---
nodes:
    mainnet: 'https://opt-mainnet.g.alchemy.com/v2/XXXXXXXXXXX'
    goerli:  'https://opt-goerli.g.alchemy.com/v2/XXXXXXXXXXX'
etherscan:
    mainnet: 'https://api-optimistic.etherscan.io/api?module=contract&action=getabi&address={}&apikey=XXXXXXXXXXX'
    goerli: 'https://api-goerli-optimism.etherscan.io/api?module=contract&action=getabi&address={}&apikey=XXXXXXXXXXX'
                
resolver:
    mainnet:  '0x95A6a3f44a70172E7d50a9e28c85Dfd712756B8C'
    goerli:  '0x1d551351613a28d676BaC1Af157799e201279198'
        
pyth:

    mainnet: 'https://xc-mainnet.pyth.network/api/latest_price_feeds?ids[]={}'

    goerli: 'https://xc-testnet.pyth.network/api/latest_price_feeds?ids[]={}'
    
```

### Run Code

#### CREATE VIRTUAL ENVIRONMENT
```python3.8 -m venv myvenv ```

#### ACTIVATE VIRTUAL ENVIRONMENT
```source myvenv/bin/activate```

#### Install Requirements
```pip install env/requirements.txt```

#### Install Requirements

```python main.py -h```

#### Compute exact liquidation price

##### Input:

```$python main.py -a 0x21d099fE94FF5075654e36d7CaF0FeFADaFe7446 -t eth -s 1 -n mainnet```

Args to be used:
- `a` being the address of the user or smart contract
- `t` being the ticker
- `s` the size, 1.5 means 1.5 eth for example, set `s` to zero for no position changes
- `n` can be `mainnet` or `goerli`

#### Output:
 
```{'liquidationPrice': 2010.5158171917135, 'safePrice': 2010.3147656099943}```

- `safePrice`: Price at which an account is safe from liquidation
- `liquidationPrice`: Price at which an account has already been liquidated

For usage, use `safePrice` in the UI and note that highly leveraged positions that exceed maxLeverage, the displayed price is an estimate as the account is very near liquidation thresholds.