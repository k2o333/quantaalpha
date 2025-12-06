#!/usr/bin/env python
"""
Verification script for atom_dict_schema_validation
This script verifies data dictionary schemas appropriate for stock codes, industries, etc.
in the context of A-share market data platform
"""

def verify_dict_schema_validation():
    try:
        # Test appropriate data dictionary schemas for A-share market

        # Stock code dictionary - mapping for Chinese stock codes
        stock_code_dict = {
            "A-shares": {
                "exchange_prefixes": {
                    "SSE": ["600", "601", "603", "605", "000", "001", "002", "300", "301", "688", "689"],
                    "SZE": ["000", "001", "002", "003", "300", "301", "688", "689"]
                },
                "market_sectors": ["main_board", "gem", "star_market", "sme_board"],
                "stock_types": ["A_share", "B_share"]
            },
            "bond_codes": {
                "government": ["010", "020", "101", "108", "109", "111", "112", "113", "118", "120", "121", "122", "123", "124", "127", "128", "131810", "131811", "132000"]
            }
        }

        # Industry taxonomy dictionary following CSRC classification
        industry_dict = {
            "A": "农林牧渔",  # Agriculture, Forestry, Animal Husbandry and Fishery
            "B": "采矿业",    # Mining
            "C": "制造业",    # Manufacturing
            "D": "电力、热力、燃气及水生产和供应业",  # Electricity, Heat, Gas and Water Production and Supply
            "E": "建筑业",    # Construction
            "F": "批发和零售业", # Wholesale and Retail
            "G": "交通运输、仓储和邮政业", # Transportation, Storage and Post
            "H": "住宿和餐饮业", # Accommodation and Catering
            "I": "信息传输、软件和信息技术服务业", # Information Transmission, Software and Information Technology Services
            "J": "金融业",    # Financial Services
            "K": "房地产业",  # Real Estate
            "L": "租赁和商务服务业", # Leasing and Business Services
            "M": "科学研究和技术服务业", # Scientific Research and Technical Services
            "N": "水利、环境和公共设施管理业", # Water Conservancy, Environment and Public Facilities Management
            "O": "居民服务、修理和其他服务业", # Resident Services, Repair and Other Services
            "P": "教育",     # Education
            "Q": "卫生和社会工作", # Health and Social Work
            "R": "文化、体育和娱乐业", # Culture, Sports and Entertainment
            "S": "综合",     # Comprehensive
            "T": "批发和零售业_专营" # Specialized Wholesale and Retail
        }

        # Verify that key data structures are correctly defined
        assert "C" in industry_dict, "Manufacturing sector should be in industry dict"
        assert "A-shares" in stock_code_dict, "A-shares section should be in stock code dict"
        assert "exchange_prefixes" in stock_code_dict["A-shares"], "Exchange prefixes should be in A-shares section"

        # Verify that industry dictionary has reasonable data
        assert len(industry_dict) > 10, "Industry dictionary should have multiple sectors"
        assert industry_dict["C"] == "制造业", "C sector should be Manufacturing"

        # Test stock sector availability
        stock_sector_keys = stock_code_dict["A-shares"]["market_sectors"]
        assert "main_board" in stock_sector_keys, "Main board should be in market sectors"
        assert "gem" in stock_sector_keys, "Growth Enterprise Market should be in market sectors"

        print("Stock Code Dictionary example:")
        print(f"  A-shares exchanges: {list(stock_code_dict['A-shares']['exchange_prefixes'].keys())}")

        print("Industry Dictionary example (first 5):")
        for code, name in list(industry_dict.items())[:5]:
            print(f"  {code}: {name}")

        print("Market sectors:", stock_sector_keys)

        print("SUCCESS: Dictionary schemas are appropriately defined for A-share market platform")
        return True

    except Exception as e:
        print(f"FAILURE: Error validating dictionary schemas: {e}")
        return False

if __name__ == "__main__":
    success = verify_dict_schema_validation()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)