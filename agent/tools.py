from langchain.tools import tool
from data import users_data
from dotenv import load_dotenv
import logging 
from objects import PurchaseItem
from datetime import date 

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format=" %(asctime)s | %(levelname)s | %(message)s "
)

@tool
def get_user_purchase_history(user:str) -> dict:
    """this tool takes the user username and return a dict of the user purchase history if the user exists
    """
    logging.info(f"using get_user_purchase history tool on user: {user}")
    if users_data.get(user):
        return users_data[user]
    return {"status": "there was no username found"}

@tool
def calculate_right_refund(user:str, items:list[PurchaseItem]) -> str:
    """this tool takes a list of the items to be returned and the username and
    will return how much the refund is worth
    """
    logging.info(f"using calculate_right_refund tool to get user's: {user} refund")
    
    if users_data.get(user):
        
        total_refund = 0
        
        for item in items:
            if users_data[user].get(item.name):
                total_refund += users_data[user][items.name]["price"]
                
        return f"the value of the refund is: {total_refund}"
    
    
    return {"status": "there was no username found"}
    
    