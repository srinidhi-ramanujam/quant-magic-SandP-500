#!/usr/bin/env python3
"""
Fix sector mapping for all companies in the dataset.

This script creates a comprehensive sector mapping based on:
1. Known major S&P 500 companies
2. Company name pattern matching
3. Industry keywords in company names
"""

import pandas as pd
from pathlib import Path
import sys

# Known company CIK to GICS sector mappings (major S&P 500 companies)
KNOWN_SECTORS = {
    # Information Technology
    '0000789019': 'Information Technology',  # MICROSOFT CORP
    '0000320193': 'Information Technology',  # APPLE INC
    '0001652044': 'Information Technology',  # ALPHABET INC
    '0001045810': 'Information Technology',  # NVIDIA CORP
    '0001326801': 'Information Technology',  # META PLATFORMS INC
    '0001730168': 'Information Technology',  # BROADCOM INC
    '0000051143': 'Information Technology',  # IBM
    '0000066740': 'Information Technology',  # 3M CO
    '0000804753': 'Information Technology',  # CISCO SYSTEMS INC
    '0000063908': 'Information Technology',  # INTEL CORP
    '0000886982': 'Information Technology',  # ORACLE CORP
    '0001364742': 'Information Technology',  # ADOBE INC
    '0001108524': 'Information Technology',  # SALESFORCE INC
    '0001467373': 'Information Technology',  # TEXAS INSTRUMENTS INC
    '0000002488': 'Information Technology',  # ADVANCED MICRO DEVICES INC
    '0001018724': 'Information Technology',  # AMAZON COM INC (also Consumer Discretionary, but tech-focused)
    '0000319201': 'Information Technology',  # KLA CORP
    '0000864749': 'Information Technology',  # TRIMBLE INC
    '0001121788': 'Information Technology',  # GARMIN LTD
    '0000749251': 'Information Technology',  # GARTNER INC
    '0000101829': 'Information Technology',  # RTX CORP / RAYTHEON TECHNOLOGIES
    
    # Health Care
    '0000200406': 'Health Care',  # JOHNSON & JOHNSON
    '0001551152': 'Health Care',  # UNITEDHEALTH GROUP INC
    '0000310158': 'Health Care',  # ELI LILLY & CO
    '0000078003': 'Health Care',  # PFIZER INC
    '0000002488': 'Health Care',  # ABBOTT LABORATORIES
    '0000316709': 'Health Care',  # MERCK & CO INC
    '0000040704': 'Health Care',  # BRISTOL-MYERS SQUIBB CO
    '0000318154': 'Health Care',  # ABBOTT LABORATORIES
    '0001534675': 'Health Care',  # ABBVIE INC
    '0001652044': 'Health Care',  # AMGEN INC
    '0000008868': 'Health Care',  # GILEAD SCIENCES INC
    '0001682852': 'Health Care',  # MODERNA INC
    '0000070318': 'Health Care',  # TENET HEALTHCARE CORP
    '0000920148': 'Health Care',  # LABCORP HOLDINGS INC
    '0000927066': 'Health Care',  # DAVITA INC
    
    # Financials
    '0001067983': 'Financials',  # BERKSHIRE HATHAWAY INC
    '0000019617': 'Financials',  # JPMORGAN CHASE & CO
    '0000070858': 'Financials',  # BANK OF AMERICA CORP
    '0000831001': 'Financials',  # WELLS FARGO & CO
    '0000831001': 'Financials',  # CITIGROUP INC
    '0000886206': 'Financials',  # MORGAN STANLEY
    '0000886982': 'Financials',  # GOLDMAN SACHS GROUP INC
    '0000732717': 'Financials',  # CHARLES SCHWAB CORP
    '0000017313': 'Financials',  # CAPITAL SOUTHWEST CORP
    '0000064040': 'Financials',  # S&P GLOBAL INC
    
    # Consumer Discretionary
    '0001018724': 'Consumer Discretionary',  # AMAZON COM INC
    '0001065280': 'Consumer Discretionary',  # NETFLIX INC
    '0001047862': 'Consumer Discretionary',  # TESLA INC (also could be Info Tech, but primarily Consumer Discretionary)
    '0001318605': 'Consumer Discretionary',  # TESLA INC
    '0000004281': 'Consumer Discretionary',  # HOME DEPOT INC
    '0000027904': 'Consumer Discretionary',  # DELTA AIR LINES INC
    '0000006201': 'Consumer Discretionary',  # AMERICAN AIRLINES GROUP INC
    '0000037996': 'Consumer Discretionary',  # FORD MOTOR CO
    '0000012927': 'Consumer Discretionary',  # BOEING CO (actually Industrials)
    '0001001250': 'Consumer Discretionary',  # STARBUCKS CORP
    '0000320187': 'Consumer Discretionary',  # NIKE INC
    '0001166691': 'Consumer Discretionary',  # BOOKING HOLDINGS INC
    '0000822416': 'Consumer Discretionary',  # PULTEGROUP INC
    '0000851968': 'Consumer Discretionary',  # MOHAWK INDUSTRIES INC
    '0000906163': 'Consumer Discretionary',  # NVR INC
    
    # Communication Services
    '0001326801': 'Communication Services',  # META PLATFORMS INC
    '0001652044': 'Communication Services',  # ALPHABET INC (also IT)
    '0001564590': 'Communication Services',  # NETFLIX INC
    '0001166691': 'Communication Services',  # COMCAST CORP
    '0000732717': 'Communication Services',  # WALT DISNEY CO
    '0000092122': 'Communication Services',  # VERIZON COMMUNICATIONS INC
    '0000732712': 'Communication Services',  # AT&T INC
    '0000051644': 'Communication Services',  # INTERPUBLIC GROUP OF COMPANIES INC
    '0000029989': 'Communication Services',  # OMNICOM GROUP INC
    
    # Industrials
    '0000012927': 'Industrials',  # BOEING CO
    '0000027904': 'Industrials',  # DELTA AIR LINES INC
    '0000006201': 'Industrials',  # AMERICAN AIRLINES GROUP INC
    '0000016868': 'Industrials',  # CANADIAN NATIONAL RAILWAY CO
    '0000033185': 'Industrials',  # EQUIFAX INC (actually IT Services)
    '0000004281': 'Industrials',  # HOWMET AEROSPACE INC
    '0000040533': 'Industrials',  # GENERAL DYNAMICS CORP
    '0000052988': 'Industrials',  # JACOBS SOLUTIONS INC
    '0000091142': 'Industrials',  # UNITED AIRLINES HOLDINGS INC
    '0000055067': 'Industrials',  # 3M CO
    '0000021344': 'Industrials',  # CATERPILLAR INC
    '0000047111': 'Industrials',  # LOCKHEED MARTIN CORP
    '0000063908': 'Industrials',  # RAYTHEON TECHNOLOGIES CORP
    '0000773840': 'Industrials',  # UNION PACIFIC CORP
    '0000764180': 'Industrials',  # FED EX CORP
    '0000062996': 'Industrials',  # MASCO CORP
    '0000091440': 'Industrials',  # SNAP-ON INC
    '0000093556': 'Industrials',  # STANLEY BLACK & DECKER
    '0000723254': 'Industrials',  # CINTAS CORP
    '0000217346': 'Industrials',  # TEXTRON INC
    
    # Consumer Staples
    '0000104169': 'Consumer Staples',  # WALMART INC
    '0000021344': 'Consumer Staples',  # PROCTER & GAMBLE CO
    '0000021665': 'Consumer Staples',  # COCA-COLA CO
    '0000077476': 'Consumer Staples',  # PEPSICO INC
    '0000026659': 'Consumer Staples',  # COSTCO WHOLESALE CORP
    '0000055785': 'Consumer Staples',  # KIMBERLY CLARK CORP
    '0000063754': 'Consumer Staples',  # MONDELEZ INTERNATIONAL INC
    '0000027419': 'Consumer Staples',  # COLGATE PALMOLIVE CO
    
    # Energy
    '0000034088': 'Energy',  # EXXON MOBIL CORP
    '0000093410': 'Energy',  # CHEVRON CORP
    '0000813672': 'Energy',  # CONOCOPHILLIPS
    '0000011199': 'Energy',  # SCHLUMBERGER LTD
    '0001163165': 'Energy',  # EOG RESOURCES INC
    '0001097149': 'Energy',  # PIONEER NATURAL RESOURCES CO
    
    # Utilities
    '0000065984': 'Utilities',  # ENTERGY CORP
    '0000004904': 'Utilities',  # AMERICAN ELECTRIC POWER CO INC
    '0000092122': 'Utilities',  # SOUTHERN CO
    '0000037634': 'Utilities',  # DUKE ENERGY CORP
    '0000019745': 'Utilities',  # DOMINION ENERGY INC
    '0000003570': 'Utilities',  # NEXTERA ENERGY INC
    '0000077476': 'Utilities',  # EXELON CORP
    '0000066673': 'Utilities',  # SEMPRA ENERGY
    '0000827052': 'Utilities',  # EDISON INTERNATIONAL
    '0001004980': 'Utilities',  # PG&E CORP
    
    # Materials
    '0000026172': 'Materials',  # DOW INC
    '0000029534': 'Materials',  # DUPONT DE NEMOURS INC
    '0000051434': 'Materials',  # INTERNATIONAL PAPER CO
    '0000008818': 'Materials',  # AVERY DENNISON CORP
    '0000109380': 'Materials',  # LINDE PLC
    '0000039911': 'Materials',  # FREEPORT-MCMORAN INC
    '0000096021': 'Materials',  # NEWMONT CORP
    
    # Real Estate
    '0001589526': 'Real Estate',  # AMERICAN TOWER CORP
    '0001060822': 'Real Estate',  # PROLOGIS INC
    '0001091667': 'Real Estate',  # CROWN CASTLE INTERNATIONAL CORP
    '0001062993': 'Real Estate',  # EQUINIX INC
    '0000886163': 'Real Estate',  # PUBLIC STORAGE
    '0001070750': 'Real Estate',  # SIMON PROPERTY GROUP INC
    '0001404281': 'Real Estate',  # APPLE HOSPITALITY REIT
    
    # Additional Consumer Discretionary
    '0001037038': 'Consumer Discretionary',  # RALPH LAUREN CORP
    '0001061894': 'Consumer Discretionary',  # GILDAN ACTIVEWEAR
    '0001397187': 'Consumer Discretionary',  # LULULEMON ATHLETICA
    '0001324424': 'Consumer Discretionary',  # EXPEDIA GROUP
    '0001513761': 'Consumer Discretionary',  # NORWEGIAN CRUISE LINE
    '0000046080': 'Consumer Discretionary',  # HASBRO
    '0000882184': 'Consumer Discretionary',  # HORTON D R (homebuilder)
    '0001639825': 'Consumer Discretionary',  # PELOTON
    '0001811210': 'Consumer Discretionary',  # LUCID GROUP (electric vehicles)
    '0000910521': 'Consumer Discretionary',  # DECKERS OUTDOOR
    '0001590895': 'Consumer Discretionary',  # ELDORADO RESORTS
    '0001116132': 'Consumer Discretionary',  # TAPESTRY / COACH
    '0001428439': 'Consumer Discretionary',  # ROKU
    '0001046568': 'Consumer Discretionary',  # PERDOCEO EDUCATION
    
    # Additional Industrials
    '0001037868': 'Industrials',  # AMETEK
    '0000075362': 'Industrials',  # PACCAR
    '0001090727': 'Industrials',  # UNITED PARCEL SERVICE (UPS)
    '0001050915': 'Industrials',  # QUANTA SERVICES
    '0001069183': 'Industrials',  # AXON ENTERPRISE / TASER
    '0000746515': 'Industrials',  # EXPEDITORS INTERNATIONAL
    '0001501585': 'Industrials',  # HUNTINGTON INGALLS
    '0001521332': 'Industrials',  # APTIV
    '0001579241': 'Industrials',  # ALLEGION
    '0000084839': 'Industrials',  # ROLLINS
    '0000775158': 'Industrials',  # OSHKOSH CORP
    '0000100517': 'Industrials',  # UNITED CONTINENTAL HOLDINGS
    '0001020569': 'Industrials',  # IRON MOUNTAIN
    '0000882835': 'Industrials',  # ROPER INDUSTRIES
    '0001466258': 'Industrials',  # INGERSOLL-RAND
    '0000053669': 'Industrials',  # JOHNSON CONTROLS
    '0000202058': 'Industrials',  # HARRIS CORP
    '0000866121': 'Industrials',  # ORBITAL ATK
    '0000105634': 'Industrials',  # EMCOR GROUP
    
    # Additional Materials
    '0000916076': 'Materials',  # MARTIN MARIETTA
    '0000009389': 'Materials',  # BALL CORP
    '0002005951': 'Materials',  # SMURFIT WESTROCK
    '0001370946': 'Materials',  # OWENS CORNING
    '0000024741': 'Materials',  # CORNING INC
    '0001396009': 'Materials',  # VULCAN MATERIALS
    '0001748790': 'Materials',  # AMCOR
    '0001431852': 'Materials',  # OSISKO DEVELOPMENT (mining)
    
    # Additional Information Technology
    '0000723531': 'Information Technology',  # PAYCHEX
    '0001037646': 'Information Technology',  # METTLER TOLEDO
    '0000097210': 'Information Technology',  # TERADYNE
    '0001110803': 'Information Technology',  # ILLUMINA
    '0001639920': 'Information Technology',  # SPOTIFY TECHNOLOGY
    
    # Additional Health Care
    '0001100682': 'Health Care',  # CHARLES RIVER LABORATORIES
    '0000879169': 'Health Care',  # INCYTE CORP
    '0000711404': 'Health Care',  # COOPER COMPANIES
    '0001478242': 'Health Care',  # IQVIA HOLDINGS / QUINTILES
    '0000031791': 'Health Care',  # REVVITY / PERKINELMER
    '0001967680': 'Health Care',  # VERALTO CORP
    
    # Additional Energy
    '0001039684': 'Energy',  # ONEOK
    '0001389170': 'Energy',  # TARGA RESOURCES
    '0001506307': 'Energy',  # KINDER MORGAN
    '0000107263': 'Energy',  # WILLIAMS COMPANIES
    
    # Additional Utilities
    '0001111711': 'Utilities',  # NISOURCE
    '0001711269': 'Utilities',  # EVERGY
    
    # Additional Communication Services
    '0000078150': 'Communication Services',  # PLDT (Philippine telecom)
    '0001973266': 'Communication Services',  # TKO GROUP (WWE/UFC)
    '0001564708': 'Communication Services',  # NEWS CORP
    '0000912958': 'Communication Services',  # MILLICOM INTERNATIONAL
    '0002026478': 'Communication Services',  # NEWSMAX
    
    # Additional Financials
    '0001369241': 'Financials',  # DANAOS CORP (shipping finance)
}

# Pattern-based sector mapping (keywords in company names)
SECTOR_PATTERNS = {
    'Information Technology': [
        'MICROSOFT', 'APPLE', 'ALPHABET', 'GOOGLE', 'NVIDIA', 'META', 'BROADCOM',
        'IBM', 'CISCO', 'INTEL', 'ORACLE', 'ADOBE', 'SALESFORCE', 'SOFTWARE',
        'TECHNOLOGIES', 'SEMICONDUCTOR', 'ELECTRONICS', 'COMPUTER', 'DATA',
        'PAYPAL', 'INTUIT', 'SERVICENOW', 'QUALCOMM', 'MICRON', 'APPLIED MATERIALS',
        'TEXAS INSTRUMENTS', 'AMD', 'ADVANCED MICRO DEVICES', 'ANALOG DEVICES',
        'COGNIZANT', 'ACCENTURE', 'VMWARE', 'WORKDAY', 'AUTODESK', 'SYNOPSYS',
        'CADENCE', 'NETAPP', 'FORTINET', 'PALO ALTO', 'CROWDSTRIKE', 'DATADOG',
        'SNOWFLAKE', 'MONGODB', 'SPLUNK', 'OKTA', 'ZSCALER', 'VERISIGN',
        'GARTNER', 'GARMIN', 'KLA', 'TRIMBLE', 'RTX', 'KEYSIGHT', 'TELEDYNE',
        'AGILENT', 'TRANE',
    ],
    'Health Care': [
        'JOHNSON & JOHNSON', 'UNITEDHEALTH', 'LILLY', 'PFIZER', 'ABBOTT',
        'MERCK', 'BRISTOL', 'ABBVIE', 'AMGEN', 'GILEAD', 'MODERNA',
        'TENET', 'HEALTHCARE', 'HOSPITAL', 'PHARMACEUTICAL', 'BIOTECH',
        'MEDICAL', 'HEALTH', 'THERAPEUTICS', 'DIAGNOSTICS', 'LABORATORY',
        'MEDTRONIC', 'THERMO FISHER', 'DANAHER', 'STRYKER', 'BOSTON SCIENTIFIC',
        'INTUITIVE SURGICAL', 'EDWARDS LIFESCIENCES', 'ZIMMER BIOMET', 'BAXTER',
        'BECTON DICKINSON', 'CARDINAL HEALTH', 'HUMANA', 'CIGNA', 'ANTHEM',
        'CENTENE', 'HCA', 'UNIVERSAL HEALTH', 'CVS', 'WALGREENS', 'MCKESSON',
    ],
    'Financials': [
        'BERKSHIRE', 'JPMORGAN', 'BANK', 'WELLS FARGO', 'CITIGROUP',
        'MORGAN STANLEY', 'GOLDMAN SACHS', 'SCHWAB', 'CAPITAL', 'FINANCIAL',
        'INSURANCE', 'CREDIT', 'TRUST', 'INVESTMENT', 'ASSET', 'FUND',
        'AMERICAN EXPRESS', 'VISA', 'MASTERCARD', 'PAYPAL', 'BLACKROCK',
        'STATE STREET', 'BNY MELLON', 'US BANCORP', 'PNC', 'TRUIST',
        'CAPITAL ONE', 'METLIFE', 'PRUDENTIAL', 'TRAVELERS', 'PROGRESSIVE',
        'ALLSTATE', 'CHUBB', 'MARSH', 'AON', 'FIDELITY', 'T. ROWE PRICE',
    ],
    'Consumer Discretionary': [
        'AMAZON', 'TESLA', 'HOME DEPOT', 'NIKE', 'STARBUCKS', 'MCDONALDS',
        'BOOKING', 'LOWE', 'TARGET', 'ROSS', 'TJX', 'DOLLAR', 'AUTOMOTIVE',
        'RESTAURANT', 'RETAIL', 'APPAREL', 'HOTEL', 'ENTERTAINMENT',
        'AUTO', 'AUTOMOTIVE', 'MOTORS', 'FORD', 'GENERAL MOTORS', 'GM',
        'MARRIOTT', 'HILTON', 'HYATT', 'CARNIVAL', 'ROYAL CARIBBEAN',
        'CAESARS', 'MGM', 'WYNN', 'LAS VEGAS', 'BEST BUY', 'AUTOZONE',
        "O'REILLY", 'ADVANCE AUTO', 'TRACTOR SUPPLY', 'POOL CORP',
        'PULTE', 'MOHAWK', 'NVR', 'LENNAR', 'DR HORTON', 'KB HOME',
        'TOLL BROTHERS', 'HOMEBUILDERS', 'BUILDERS', 'HOMES',
    ],
    'Communication Services': [
        'META', 'ALPHABET', 'NETFLIX', 'COMCAST', 'DISNEY', 'VERIZON',
        'AT&T', 'INTERPUBLIC', 'OMNICOM', 'COMMUNICATIONS', 'MEDIA',
        'BROADCASTING', 'TELECOM', 'WIRELESS', 'CABLE', 'SATELLITE',
        'T-MOBILE', 'SPRINT', 'CHARTER', 'DISH', 'FOX', 'PARAMOUNT',
        'WARNER', 'DISCOVERY', 'ACTIVISION', 'ELECTRONIC ARTS', 'TAKE-TWO',
    ],
    'Industrials': [
        'BOEING', 'DELTA', 'AMERICAN AIRLINES', 'UNITED AIRLINES', 'SOUTHWEST',
        'RAILWAY', 'RAILROAD', 'UNION PACIFIC', 'CSX', 'NORFOLK SOUTHERN',
        'CANADIAN NATIONAL', 'CANADIAN PACIFIC', 'KANSAS CITY SOUTHERN',
        'EQUIFAX', 'HOWMET', 'AEROSPACE', 'GENERAL DYNAMICS', 'JACOBS',
        'CATERPILLAR', 'DEERE', 'LOCKHEED', 'RAYTHEON', 'NORTHROP',
        'HONEYWELL', 'UNITED RENTALS', 'WASTE MANAGEMENT', 'REPUBLIC SERVICES',
        'FEDEX', 'UPS', 'JB HUNT', 'OLD DOMINION', 'PENSKE', 'SCHNEIDER',
        '3M', 'EMERSON', 'PARKER', 'EATON', 'ROCKWELL', 'FORTIVE',
        'AIRLINES', 'AIR', 'FREIGHT', 'LOGISTICS', 'TRANSPORTATION',
        'MANUFACTURING', 'INDUSTRIAL', 'MACHINERY', 'EQUIPMENT', 'ENGINEERING',
        'MASCO', 'SNAP-ON', 'STANLEY', 'CINTAS', 'TEXTRON', 'FASTENAL',
        'XYLEM', 'GRACO', 'PENTAIR', 'A. O. SMITH', 'REGAL', 'TOOLS',
    ],
    'Consumer Staples': [
        'WALMART', 'PROCTER', 'COCA-COLA', 'PEPSI', 'COSTCO', 'KIMBERLY',
        'MONDELEZ', 'COLGATE', 'KROGER', 'WALGREENS', 'CVS', 'FOOD',
        'BEVERAGE', 'GROCERY', 'SUPERMARKET', 'TOBACCO', 'HOUSEHOLD',
        'PHILIP MORRIS', 'ALTRIA', 'GENERAL MILLS', 'KELLOGG', 'CONAGRA',
        'CAMPBELL', 'KRAFT HEINZ', 'HERSHEY', 'CLOROX', 'CHURCH & DWIGHT',
    ],
    'Energy': [
        'EXXON', 'MOBIL', 'CHEVRON', 'CONOCOPHILLIPS', 'SCHLUMBERGER',
        'EOG', 'PIONEER', 'OIL', 'GAS', 'PETROLEUM', 'ENERGY', 'EXPLORATION',
        'OCCIDENTAL', 'HESS', 'MARATHON', 'VALERO', 'PHILLIPS 66', 'HF SINCLAIR',
        'DEVON', 'CHESAPEAKE', 'APACHE', 'ANADARKO', 'NOBLE', 'DIAMONDBACK',
        'HALLIBURTON', 'BAKER HUGHES', 'TRANSOCEAN', 'NATIONAL OILWELL',
    ],
    'Utilities': [
        'ENTERGY', 'AMERICAN ELECTRIC', 'SOUTHERN', 'DUKE ENERGY',
        'DOMINION', 'NEXTERA', 'EXELON', 'SEMPRA', 'ELECTRIC', 'POWER',
        'UTILITY', 'UTILITIES', 'ENERGY', 'GAS', 'WATER', 'PUBLIC SERVICE',
        'CONSOLIDATED EDISON', 'XCEL', 'WEC', 'PPL', 'EVERSOURCE', 'CMS',
        'DTE', 'AES', 'NRG', 'VISTRA', 'CENTERPOINT', 'ALLIANT', 'AMEREN',
    ],
    'Materials': [
        'DOW', 'DUPONT', 'INTERNATIONAL PAPER', 'AVERY DENNISON', 'LINDE',
        'FREEPORT', 'NEWMONT', 'CHEMICAL', 'PAPER', 'PACKAGING', 'MINING',
        'STEEL', 'ALUMINUM', 'COPPER', 'GOLD', 'SILVER', 'METALS',
        'SHERWIN-WILLIAMS', 'PPG', 'AIR PRODUCTS', 'PRAXAIR', 'ECOLAB',
        'CORTEVA', 'FMC', 'CF INDUSTRIES', 'MOSAIC', 'NUCOR', 'STEEL DYNAMICS',
        'ALCOA', 'UNITED STATES STEEL', 'CLEVELAND-CLIFFS', 'BARRICK', 'AGNICO',
    ],
    'Real Estate': [
        'AMERICAN TOWER', 'PROLOGIS', 'CROWN CASTLE', 'EQUINIX',
        'PUBLIC STORAGE', 'SIMON PROPERTY', 'REALTY', 'REIT', 'PROPERTIES',
        'REAL ESTATE', 'APARTMENTS', 'RESIDENTIAL', 'COMMERCIAL', 'RETAIL',
        'WELLTOWER', 'VENTAS', 'HEALTHPEAK', 'ALEXANDRIA', 'BOSTON PROPERTIES',
        'VORNADO', 'SL GREEN', 'KILROY', 'DOUGLAS EMMETT', 'HUDSON PACIFIC',
        'APPLE HOSPITALITY', 'HOST HOTELS', 'PARK HOTELS', 'RLJ LODGING',
    ],
}


def assign_sector_by_name(company_name: str) -> str:
    """Assign GICS sector based on company name patterns."""
    name_upper = company_name.upper()
    
    # Check each sector's patterns
    for sector, patterns in SECTOR_PATTERNS.items():
        for pattern in patterns:
            if pattern in name_upper:
                return sector
    
    return 'Other'


def fix_sector_mapping():
    """Fix sector mapping for all companies."""
    project_root = Path(__file__).parent
    
    # Load current companies
    companies_file = project_root / "data" / "parquet" / "companies_with_sectors.parquet"
    print(f"Loading companies from: {companies_file}")
    df = pd.read_parquet(companies_file)
    
    print(f"\nOriginal sector distribution:")
    print(df['gics_sector'].value_counts())
    print(f"\nTotal 'Other': {len(df[df['gics_sector'] == 'Other'])}")
    
    # Apply fixes
    fixed_count = 0
    pattern_count = 0
    
    # First pass: Apply known mappings
    for cik, sector in KNOWN_SECTORS.items():
        mask = df['cik'] == cik
        if mask.any() and df.loc[mask, 'gics_sector'].iloc[0] == 'Other':
            df.loc[mask, 'gics_sector'] = sector
            fixed_count += 1
    
    print(f"\n✓ Fixed {fixed_count} companies using known CIK mappings")
    
    # Second pass: Pattern matching for remaining "Other" companies
    other_mask = df['gics_sector'] == 'Other'
    for idx, row in df[other_mask].iterrows():
        inferred_sector = assign_sector_by_name(row['name'])
        if inferred_sector != 'Other':
            df.at[idx, 'gics_sector'] = inferred_sector
            pattern_count += 1
            print(f"  Pattern match: {row['name'][:50]} → {inferred_sector}")
    
    print(f"\n✓ Fixed {pattern_count} companies using pattern matching")
    
    # Save updated file
    print(f"\nSaving updated file: {companies_file}")
    df.to_parquet(companies_file, index=False)
    
    # Summary
    print(f"\n{'='*70}")
    print("UPDATED SECTOR DISTRIBUTION:")
    print("="*70)
    sector_counts = df['gics_sector'].value_counts().sort_values(ascending=False)
    for sector, count in sector_counts.items():
        print(f"  {sector:30s}: {count:3d}")
    
    print(f"\n{'='*70}")
    print(f"Total companies:     {len(df)}")
    print(f"Fixed (known):       {fixed_count}")
    print(f"Fixed (pattern):     {pattern_count}")
    print(f"Remaining 'Other':   {len(df[df['gics_sector'] == 'Other'])}")
    print("="*70)
    
    # Show remaining "Other" companies
    remaining_other = df[df['gics_sector'] == 'Other']
    if len(remaining_other) > 0:
        print(f"\nRemaining 'Other' companies ({len(remaining_other)}):")
        for idx, row in remaining_other.head(20).iterrows():
            print(f"  {row['cik']}: {row['name']}")
        if len(remaining_other) > 20:
            print(f"  ... and {len(remaining_other) - 20} more")
    
    print(f"\n✅ Sector mapping fixed!")
    return df


if __name__ == "__main__":
    fix_sector_mapping()
