from utils.liquidation_price import LiquidationPrice
import argparse
from argparse import RawTextHelpFormatter
from utils.utility import parse_yaml

conf        = parse_yaml(r"config/conf.yaml")

if __name__ == '__main__':

    description = \
    '''
    To calculate an accurate liquidation price for the Synthetix Perps V2 Markets
    
    Calculates the liquidation price of account 0x21d099fE94FF5075654e36d7CaF0FeFADaFe7446 
    after he adds 1 eth to his existing position
        python main.py -a 0x21d099fE94FF5075654e36d7CaF0FeFADaFe7446 -t eth -s 1 -n mainnet

    Calculates the liquidation price of the existing position of account 0x21d099fE94FF5075654e36d7CaF0FeFADaFe7446
        python main.py -a 0x21d099fE94FF5075654e36d7CaF0FeFADaFe7446 -t eth -s 0 -n goerli
    
    output:        
    {'liquidationPrice': 1796.0074931733768, 'safePrice': 1794.9305348524654}

    
    '''
    parser = argparse.ArgumentParser(description=description,formatter_class=RawTextHelpFormatter)

    parser.add_argument("-a",
                        type=str,
                        required=True,
                        help="enter the user address")    

    parser.add_argument("-t",
                        type=str,
                        required=True,
                        help="enter the ticker, i.e. one of eth, btc, link")

    parser.add_argument("-s",
                        type=float,
                        required=True,
                        help="enter the size of the position, 1 means 1 ether, 0 means existing position")

    parser.add_argument("-n",
                        type=str,
                        choices=['goerli','mainnet'],
                        required=True,
                        help="enter the network goerli or mainnet")

    args = parser.parse_args()
    
    lpc = LiquidationPrice(conf=conf,network=args.n)
    lp  = lpc.fetch_exact_liquidation_price(accountAddress=args.a, ticker=args.t, sizeDelta=args.s)
    print(lp)

