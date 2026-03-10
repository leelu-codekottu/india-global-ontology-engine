"""
expand_knowledge_graph.py
========================
Massive knowledge graph expansion across 6 domains:
  1. Geopolitics  2. Economics  3. Defense  4. Technology  5. Climate  6. Society

Workflow:
  Phase 1: Load verified CSV data (nodes.csv + edges.csv)
  Phase 2: Generate 1000+ new nodes with edges across all domains
  Phase 3: LLM double-check verification using Groq
  Phase 4: Insert verified data into Memgraph

Run:
  python -m scripts.expand_knowledge_graph
"""

import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import GROQ_API_KEY, DATA_DIR
from src.graph.memgraph_init import get_memgraph, create_constraints, create_indexes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(DATA_DIR / "kg_expansion.log"),
    ],
)
logger = logging.getLogger(__name__)

NOW = datetime.now(timezone.utc).isoformat()

# ═══════════════════════════════════════════════════════════════════
# LABEL MAPPING for CSV type column → Memgraph label
# ═══════════════════════════════════════════════════════════════════
TYPE_TO_LABEL = {
    "country": "Country",
    "location": "Location",
    "resource": "Resource",
    "event": "Event",
    "indicator": "Indicator",
    "economicindicator": "Indicator",
    "organization": "Organization",
    "company": "Company",
    "policy": "Policy",
    "person": "Person",
    "technology": "Technology",
    "vessel": "Vessel",
    "militaryasset": "MilitaryAsset",
    "agreement": "Agreement",
    "infrastructure": "Infrastructure",
}

# ═══════════════════════════════════════════════════════════════════
# PHASE 1: Read csvs
# ═══════════════════════════════════════════════════════════════════
def load_csv_data():
    """Load and verify nodes.csv and edges.csv."""
    nodes_path = DATA_DIR / "nodes.csv"
    edges_path = DATA_DIR / "edges.csv"

    nodes = {}
    with open(nodes_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nid = row["id"].strip()
            name = row["name"].strip().lower()
            ntype = row["type"].strip().lower()
            label = TYPE_TO_LABEL.get(ntype, "Event")
            nodes[name] = {
                "id": nid,
                "name": name,
                "label": label,
                "description": row.get("description", "").strip(),
                "source_url": row.get("source_url", "").strip(),
            }

    edges = []
    with open(edges_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            src = row["source"].strip().lower()
            tgt = row["target"].strip().lower()
            rel = row["relationship"].strip().upper()
            conf = float(row.get("confidence", 0.9))
            url = row.get("source_url", "").strip()
            edges.append({
                "source": src,
                "target": tgt,
                "relationship": rel,
                "confidence": conf,
                "source_url": url,
            })

    logger.info("CSV loaded: %d nodes, %d edges", len(nodes), len(edges))
    return nodes, edges


# ═══════════════════════════════════════════════════════════════════
# PHASE 2: Generate comprehensive knowledge base
# ═══════════════════════════════════════════════════════════════════

def generate_geopolitics_nodes():
    """Generate geopolitics domain nodes: countries, orgs, alliances, conflicts."""
    nodes = [
        # === COUNTRIES (expanding beyond CSV) ===
        ("afghanistan", "Country", "Central Asian nation bordering Iran and Pakistan, Taliban governed since 2021"),
        ("turkey", "Country", "NATO member and regional power straddling Europe and Asia, controls Bosphorus strait"),
        ("egypt", "Country", "North African nation controlling the Suez Canal, key US ally in Middle East"),
        ("iraq", "Country", "Middle Eastern nation with major oil reserves, host to US military bases"),
        ("syria", "Country", "Middle Eastern nation experiencing prolonged civil conflict, Russian military base host"),
        ("jordan", "Country", "Middle Eastern kingdom strategically located, hosts US military presence"),
        ("kuwait", "Country", "Gulf state and major oil exporter, hosts US military base Camp Arifjan"),
        ("bahrain", "Country", "Gulf state hosting US Navy Fifth Fleet headquarters"),
        ("lebanon", "Country", "Eastern Mediterranean nation, Hezbollah stronghold linked to Iran"),
        ("yemen", "Country", "Middle Eastern nation base for Houthi militants disrupting Red Sea shipping"),
        ("germany", "Country", "European economic powerhouse and NATO member, major manufacturing hub"),
        ("france", "Country", "European nuclear power, permanent UN Security Council member, arms exporter"),
        ("italy", "Country", "European G7 nation, key Mediterranean naval power"),
        ("spain", "Country", "European NATO member controlling Strait of Gibraltar access"),
        ("greece", "Country", "Southeast European NATO member, major shipping nation"),
        ("brazil", "Country", "South American BRICS member, major agricultural and mining exporter"),
        ("south_africa", "Country", "African BRICS member, key mineral exporter and regional power"),
        ("nigeria", "Country", "Africa's largest economy and major oil producer"),
        ("ethiopia", "Country", "East African nation with strategic location near Red Sea"),
        ("kenya", "Country", "East African nation with major Indian Ocean port of Mombasa"),
        ("indonesia", "Country", "Southeast Asian archipelago, largest Muslim-majority nation, key trade route"),
        ("malaysia", "Country", "Southeast Asian nation controlling Strait of Malacca, major palm oil exporter"),
        ("singapore", "Country", "City-state controlling key Strait of Malacca chokepoint, global financial hub"),
        ("vietnam", "Country", "Southeast Asian nation with growing manufacturing sector and South China Sea claims"),
        ("philippines", "Country", "Southeast Asian nation with contested South China Sea territories"),
        ("thailand", "Country", "Southeast Asian nation and major rice exporter"),
        ("myanmar", "Country", "Southeast Asian nation with China-backed pipelines to Bay of Bengal"),
        ("australia", "Country", "Indo-Pacific nation, AUKUS member, major mineral and LNG exporter"),
        ("new_zealand", "Country", "Pacific nation and Five Eyes intelligence alliance member"),
        ("canada", "Country", "North American nation, G7 member, major oil sands and potash exporter"),
        ("mexico", "Country", "North American nation, major US trade partner and oil producer"),
        ("argentina", "Country", "South American nation with Vaca Muerta shale formation and lithium reserves"),
        ("chile", "Country", "South American nation with world's largest copper reserves and lithium deposits"),
        ("colombia", "Country", "South American nation and major coal exporter"),
        ("venezuela", "Country", "South American nation with largest proven oil reserves, under US sanctions"),
        ("north_korea", "Country", "East Asian nuclear-armed state under comprehensive international sanctions"),
        ("taiwan", "Country", "East Asian democracy and global semiconductor manufacturing hub"),
        ("mongolia", "Country", "Central Asian nation between Russia and China with rare earth deposits"),
        ("kazakhstan", "Country", "Central Asian nation with major uranium and oil reserves, CPC pipeline to Russia"),
        ("uzbekistan", "Country", "Central Asian nation on the INSTC route with natural gas reserves"),
        ("turkmenistan", "Country", "Central Asian nation with major natural gas reserves, TAPI pipeline originator"),
        ("azerbaijan", "Country", "South Caucasus nation and Caspian oil producer, BTC pipeline originator"),
        ("georgia", "Country", "South Caucasus nation on the INSTC and BTC pipeline route"),
        ("ukraine", "Country", "Eastern European nation in active conflict with Russia since 2022"),
        ("poland", "Country", "Eastern European NATO member and key logistics hub for Ukraine support"),
        ("romania", "Country", "Southeast European NATO member hosting Aegis Ashore missile defense"),
        ("sweden", "Country", "Nordic nation that joined NATO in 2024, major submarine builder"),
        ("finland", "Country", "Nordic nation that joined NATO in 2023, 1340km border with Russia"),
        ("norway", "Country", "Nordic nation and major European natural gas supplier"),
        ("denmark", "Country", "Nordic nation controlling Greenland with rare earth and strategic minerals"),
        ("netherlands", "Country", "European nation hosting ASML, critical for semiconductor lithography"),
        ("switzerland", "Country", "European nation hosting key international organizations, major financial center"),
        ("belgium", "Country", "European nation hosting NATO and EU headquarters in Brussels"),
        ("austria", "Country", "Central European nation and key natural gas transit hub"),
        ("czech_republic", "Country", "Central European NATO member with defense electronics industry"),
        ("hungary", "Country", "Central European EU member with close ties to Russia and China"),
        ("serbia", "Country", "Balkan nation with close ties to Russia and China, non-NATO"),
        ("morocco", "Country", "North African nation with phosphate reserves and migration gateway to Europe"),
        ("algeria", "Country", "North African nation and major natural gas supplier to Europe"),
        ("libya", "Country", "North African nation with large oil reserves and ongoing instability"),
        ("tunisia", "Country", "North African nation and key Mediterranean migration transit point"),
        ("sudan", "Country", "East African nation with Red Sea coast access and internal conflict"),
        ("djibouti", "Country", "Horn of Africa nation hosting military bases for US, China, France, Japan"),
        ("somalia", "Country", "Horn of Africa nation facing piracy and Al-Shabaab insurgency"),
        ("eritrea", "Country", "Horn of Africa nation on Red Sea with Assab port"),
        ("ghana", "Country", "West African nation with offshore oil and gold reserves"),
        ("democratic_republic_of_congo", "Country", "Central African nation with 70% of global cobalt reserves"),
        ("zambia", "Country", "Southern African nation and major copper producer"),
        ("zimbabwe", "Country", "Southern African nation with lithium and platinum group metals"),
        ("namibia", "Country", "Southern African nation with uranium and emerging hydrogen potential"),
        ("angola", "Country", "Southern African nation and major African oil producer"),
        ("mozambique", "Country", "Southeast African nation with massive LNG reserves in Rovuma Basin"),
        ("tanzania", "Country", "East African nation with natural gas reserves and Bagamoyo port project"),
        ("madagascar", "Country", "Island nation in Indian Ocean with rare earth and nickel deposits"),
        ("fiji", "Country", "Pacific island nation vulnerable to climate change and sea level rise"),
        ("maldives", "Country", "Indian Ocean nation strategically located and vulnerable to sea level rise"),
        ("nepal", "Country", "South Asian landlocked nation between India and China with hydropower potential"),
        ("bhutan", "Country", "South Asian nation between India and China with hydropower exports to India"),
        ("cambodia", "Country", "Southeast Asian nation with Chinese-built Ream naval base concerns"),
        ("laos", "Country", "Southeast Asian landlocked nation with China-Laos railway and hydropower dams"),
        ("brunei", "Country", "Southeast Asian nation with oil/gas reserves and South China Sea claims"),

        # === ORGANIZATIONS (expanding beyond CSV) ===
        ("united_nations", "Organization", "Global intergovernmental organization with 193 member states"),
        ("nato", "Organization", "North Atlantic military alliance of 32 member states"),
        ("european_union", "Organization", "Political and economic union of 27 European member states"),
        ("brics", "Organization", "Bloc of major emerging economies: Brazil, Russia, India, China, South Africa plus new members"),
        ("g7", "Organization", "Group of seven advanced economies coordinating economic and security policy"),
        ("g20", "Organization", "Forum of 20 major economies representing 85% of global GDP"),
        ("asean", "Organization", "Association of Southeast Asian Nations with 10 member states"),
        ("opec", "Organization", "Organization of Petroleum Exporting Countries coordinating oil production quotas"),
        ("opec_plus", "Organization", "Extended OPEC alliance including Russia coordinating oil market management"),
        ("sco", "Organization", "Shanghai Cooperation Organisation for Eurasian security and economic cooperation"),
        ("quad", "Organization", "Quadrilateral Security Dialogue between US, India, Japan, Australia"),
        ("aukus", "Organization", "Trilateral security pact between Australia, UK, and US for nuclear submarines"),
        ("five_eyes", "Organization", "Intelligence alliance of US, UK, Canada, Australia, New Zealand"),
        ("gcc", "Organization", "Gulf Cooperation Council of six Persian Gulf monarchies"),
        ("african_union", "Organization", "Continental organization of 55 African member states"),
        ("arab_league", "Organization", "Regional organization of 22 Arabic-speaking nations"),
        ("iaea", "Organization", "International Atomic Energy Agency monitoring nuclear programs"),
        ("imf", "Organization", "International Monetary Fund providing financial stability and lending"),
        ("world_bank", "Organization", "International financial institution providing development loans"),
        ("wto", "Organization", "World Trade Organization governing international trade rules"),
        ("who", "Organization", "World Health Organization directing international public health"),
        ("interpol", "Organization", "International Criminal Police Organization facilitating global law enforcement"),
        ("fatf", "Organization", "Financial Action Task Force setting anti-money laundering standards"),
        ("rbi", "Organization", "Reserve Bank of India managing monetary policy and forex reserves"),
        ("fed", "Organization", "US Federal Reserve setting US monetary policy impacting global markets"),
        ("ecb", "Organization", "European Central Bank managing eurozone monetary policy"),
        ("pboc", "Organization", "People's Bank of China managing Chinese monetary policy"),
        ("boj", "Organization", "Bank of Japan managing Japanese monetary policy"),
        ("swift", "Organization", "Global interbank financial messaging system used for sanctions enforcement"),
        ("aiib", "Organization", "Asian Infrastructure Investment Bank led by China for development financing"),
        ("ndb", "Organization", "New Development Bank established by BRICS for development projects"),
        ("adb", "Organization", "Asian Development Bank providing development funding across Asia-Pacific"),
        ("hezbollah", "Organization", "Iranian-backed Lebanese militant group and political party"),
        ("hamas", "Organization", "Palestinian militant organization governing Gaza"),
        ("isis", "Organization", "Transnational Islamist militant organization"),
        ("al_qaeda", "Organization", "Transnational jihadist organization"),
        ("al_shabaab", "Organization", "Al-Qaeda affiliated militant group in Somalia"),
        ("pla", "Organization", "People's Liberation Army: China's unified military force"),
        ("pla_navy", "Organization", "People's Liberation Army Navy expanding Indo-Pacific presence"),
        ("indian_navy", "Organization", "Indian Navy conducting Indian Ocean patrols and anti-piracy operations"),
        ("us_centcom", "Organization", "US Central Command overseeing Middle East military operations"),
        ("us_indopacom", "Organization", "US Indo-Pacific Command managing Asia-Pacific military strategy"),
        ("wagner_group", "Organization", "Russian private military company operating in Africa and Middle East"),
        ("isro", "Organization", "Indian Space Research Organisation developing space and satellite capabilities"),
        ("nasa", "Organization", "US space agency leading space exploration and satellite programs"),
        ("csa", "Organization", "China National Space Administration developing space capabilities"),
        ("esa", "Organization", "European Space Agency coordinating European space programs"),
        ("icj", "Organization", "International Court of Justice adjudicating interstate disputes"),
        ("icc", "Organization", "International Criminal Court prosecuting war crimes and crimes against humanity"),
        ("bri", "Organization", "Belt and Road Initiative: China-led global infrastructure investment program"),

        # === EVENTS (expanding) ===
        ("russia_ukraine_war", "Event", "Ongoing military conflict since February 2022 disrupting global energy and food markets"),
        ("red_sea_crisis", "Event", "Sustained Houthi attacks on commercial shipping altering global trade routes since late 2023"),
        ("covid_19_pandemic", "Event", "Global pandemic 2020-2023 causing unprecedented supply chain disruptions"),
        ("2024_us_election", "Event", "US presidential election returning Trump to office affecting global alliances"),
        ("gaza_conflict_2023", "Event", "Israel-Hamas conflict beginning October 2023 destabilizing regional security"),
        ("sudan_civil_war", "Event", "Civil war in Sudan since April 2023 causing humanitarian crisis"),
        ("myanmar_coup", "Event", "Military coup in Myanmar February 2021 destabilizing Southeast Asian security"),
        ("taiwan_strait_tensions", "Event", "Recurring military tensions between China and Taiwan threatening semiconductor supply"),
        ("south_china_sea_disputes", "Event", "Territorial disputes in South China Sea involving multiple claimant nations"),
        ("arctic_resource_competition", "Event", "Growing competition for Arctic resources and shipping routes due to ice melt"),
        ("global_semiconductor_shortage", "Event", "Worldwide chip shortage 2020-2023 affecting automotive and electronics sectors"),
        ("2025_india_china_border_talks", "Event", "Diplomatic efforts to resolve LAC disputes and normalize India-China relations"),
        ("2026_global_recession_risk", "Event", "Growing risk of global recession due to energy shocks and trade disruptions"),
        ("suez_canal_ever_given", "Event", "2021 Suez Canal blockage highlighting global chokepoint vulnerabilities"),
        ("nord_stream_sabotage", "Event", "September 2022 sabotage of Nord Stream pipelines disrupting European gas supply"),

        # === POLICIES ===
        ("paris_climate_agreement", "Policy", "2015 global agreement to limit temperature rise to 1.5°C above pre-industrial levels"),
        ("us_ira", "Policy", "US Inflation Reduction Act 2022 providing $369B for clean energy and climate"),
        ("eu_cbam", "Policy", "EU Carbon Border Adjustment Mechanism imposing carbon tariffs on imports"),
        ("eu_green_deal", "Policy", "European Green Deal targeting climate neutrality by 2050"),
        ("india_national_hydrogen_mission", "Policy", "India's policy to develop green hydrogen production and export capacity"),
        ("make_in_india", "Policy", "Indian manufacturing initiative promoting domestic production"),
        ("atmanirbhar_bharat", "Policy", "India self-reliance policy reducing import dependencies"),
        ("china_made_in_china_2025", "Policy", "Chinese industrial policy for high-tech manufacturing self-sufficiency"),
        ("us_chips_act", "Policy", "US CHIPS and Science Act 2022 providing $52B for domestic semiconductor manufacturing"),
        ("japan_economic_security_act", "Policy", "Japan 2022 law securing critical supply chains and technology"),
        ("india_pli_scheme", "Policy", "Production Linked Incentive scheme promoting manufacturing in 14 sectors"),
        ("us_maximum_pressure_iran", "Policy", "US comprehensive sanctions campaign against Iran's economy"),
        ("jcpoa", "Policy", "Joint Comprehensive Plan of Action - 2015 Iran nuclear deal"),
        ("rcep", "Policy", "Regional Comprehensive Economic Partnership - largest free trade agreement"),
        ("cptpp", "Policy", "Comprehensive and Progressive Trans-Pacific Partnership trade agreement"),
        ("india_uae_cepa", "Policy", "India-UAE Comprehensive Economic Partnership Agreement 2022"),
        ("india_australia_ecta", "Policy", "India-Australia Economic Cooperation and Trade Agreement 2022"),
        ("african_continental_free_trade_area", "Policy", "AfCFTA creating world's largest free trade area by member states"),
        ("new_start_treaty", "Policy", "US-Russia nuclear arms reduction treaty expired/suspended"),
        ("un_arms_trade_treaty", "Policy", "International treaty regulating conventional arms transfers"),
        ("india_defense_procurement_policy", "Policy", "Indian policy prioritizing indigenous defense manufacturing"),
        ("eu_critical_raw_materials_act", "Policy", "EU policy to secure supply of critical minerals"),
    ]
    return nodes


def generate_economics_nodes():
    """Generate economics domain nodes: trade, commodities, indicators, infrastructure."""
    nodes = [
        # === RESOURCES / COMMODITIES ===
        ("natural_gas", "Resource", "Fossil fuel and feedstock, major global energy commodity"),
        ("coal", "Resource", "Fossil fuel for power generation, India is second largest importer"),
        ("uranium", "Resource", "Nuclear fuel for power generation, Kazakhstan largest producer"),
        ("iron_ore", "Resource", "Primary steelmaking raw material, Australia and Brazil top exporters"),
        ("copper", "Resource", "Critical industrial metal for electronics and renewable energy infrastructure"),
        ("lithium", "Resource", "Critical mineral for batteries and electric vehicles, lithium triangle in South America"),
        ("cobalt", "Resource", "Critical mineral for batteries, 70% sourced from Democratic Republic of Congo"),
        ("rare_earth_elements", "Resource", "17 minerals critical for electronics, EV motors, wind turbines; China controls 60% processing"),
        ("nickel", "Resource", "Battery material and stainless steel component, Indonesia dominant producer"),
        ("platinum_group_metals", "Resource", "Catalysts and hydrogen fuel cells, South Africa dominant supplier"),
        ("gold", "Resource", "Precious metal and reserve asset, India second largest consumer"),
        ("silver", "Resource", "Industrial metal used in solar panels and electronics"),
        ("aluminum", "Resource", "Light industrial metal, India fourth largest producer"),
        ("steel", "Resource", "Industrial construction material, India second largest producer globally"),
        ("wheat", "Resource", "Staple food grain, India largest producer after China"),
        ("rice", "Resource", "Staple food grain, India is world's largest exporter"),
        ("palm_oil", "Resource", "Edible oil commodity, India is world's largest importer"),
        ("sugar", "Resource", "Agricultural commodity, India is largest consumer and second largest producer"),
        ("cotton", "Resource", "Agricultural commodity for textile industry, India second largest producer"),
        ("tea", "Resource", "Agricultural commodity, India second largest producer after China"),
        ("coffee", "Resource", "Agricultural commodity, India seventh largest producer"),
        ("rubber", "Resource", "Industrial commodity for automotive and manufacturing sectors"),
        ("tin", "Resource", "Industrial metal critical for semiconductor soldering"),
        ("zinc", "Resource", "Industrial metal for galvanization and alloys"),
        ("manganese", "Resource", "Steel additive and battery material, India significant producer"),
        ("bauxite", "Resource", "Aluminum ore, India fifth largest reserves globally"),
        ("graphite", "Resource", "Critical mineral for batteries and nuclear reactors"),
        ("silicon", "Resource", "Semiconductor and solar panel base material"),
        ("helium", "Resource", "Noble gas critical for MRI machines, semiconductor manufacturing, and space"),
        ("potash", "Resource", "Fertilizer raw material, India major importer from Canada and Belarus"),
        ("phosphate", "Resource", "Fertilizer raw material, Morocco holds 70% of global reserves"),
        ("semiconductors", "Resource", "Integrated circuits critical for modern technology and defense systems"),
        ("solar_panels", "Resource", "Photovoltaic modules for renewable energy, China dominates manufacturing"),
        ("ev_batteries", "Resource", "Lithium-ion batteries for electric vehicles, key supply chain competition"),
        ("hydrogen", "Resource", "Clean fuel and industrial feedstock, emerging as key energy carrier"),
        ("ammonia", "Resource", "Chemical for fertilizers and potential clean fuel carrier"),

        # === ECONOMIC INDICATORS ===
        ("gdp_india", "Indicator", "India GDP approximately $3.9 trillion in 2025, fifth largest globally"),
        ("gdp_china", "Indicator", "China GDP approximately $18.5 trillion, second largest globally"),
        ("gdp_usa", "Indicator", "US GDP approximately $28 trillion, largest globally"),
        ("us_dollar_index", "Indicator", "DXY measuring USD against basket of currencies, global reserve currency"),
        ("indian_rupee_exchange_rate", "Indicator", "INR/USD exchange rate affected by oil prices and capital flows"),
        ("chinese_yuan_exchange_rate", "Indicator", "CNY/USD exchange rate managed by PBOC"),
        ("brent_crude_price", "Indicator", "Global benchmark crude oil price, key driver of inflation"),
        ("wti_crude_price", "Indicator", "US benchmark crude oil price"),
        ("baltic_dry_index", "Indicator", "Shipping cost index for dry bulk commodities"),
        ("global_food_price_index", "Indicator", "FAO index tracking international food commodity prices"),
        ("india_current_account_deficit", "Indicator", "India's CAD as percentage of GDP, sensitive to oil prices"),
        ("india_fiscal_deficit", "Indicator", "Government budget deficit affecting economic stability"),
        ("india_forex_reserves", "Indicator", "RBI foreign exchange reserves, approximately $600B in 2025"),
        ("india_cpi", "Indicator", "Consumer Price Index measuring India's retail inflation"),
        ("india_wpi", "Indicator", "Wholesale Price Index measuring India's producer inflation"),
        ("us_federal_funds_rate", "Indicator", "US central bank interest rate affecting global capital flows"),
        ("india_repo_rate", "Indicator", "RBI policy rate affecting lending and inflation"),
        ("global_debt_to_gdp", "Indicator", "Worldwide government debt as percentage of GDP"),
        ("india_unemployment_rate", "Indicator", "India's employment metric tracked by CMIE and NSO"),
        ("china_pmi", "Indicator", "China Purchasing Managers Index indicating manufacturing health"),
        ("shipping_insurance_rates", "Indicator", "Marine insurance premiums affected by conflict zones"),
        ("global_trade_volume", "Indicator", "Total volume of international goods trade"),
        ("india_fdi_inflows", "Indicator", "Foreign direct investment into India"),
        ("india_it_exports", "Indicator", "India's information technology services exports"),

        # === TRADE ROUTES & INFRASTRUCTURE ===
        ("suez_canal", "Location", "Egyptian waterway handling 12-15% of global trade"),
        ("panama_canal", "Location", "Central American waterway connecting Atlantic and Pacific oceans"),
        ("strait_of_malacca", "Location", "Southeast Asian chokepoint handling 25% of global shipping"),
        ("bosphorus_strait", "Location", "Turkish strait connecting Black Sea to Mediterranean"),
        ("cape_of_good_hope", "Location", "Southern African shipping route alternative to Suez"),
        ("strait_of_gibraltar", "Location", "Western Mediterranean chokepoint between Europe and Africa"),
        ("hormuz_island", "Location", "Strategic island in the Strait of Hormuz"),
        ("persian_gulf", "Location", "Body of water bordered by major oil-producing nations"),
        ("arabian_sea", "Location", "Body of water critical for India's maritime trade routes"),
        ("indian_ocean", "Location", "Third largest ocean, vital for global trade and energy transport"),
        ("south_china_sea", "Location", "Contested waterway handling one-third of global shipping"),
        ("red_sea", "Location", "Waterway connecting Mediterranean to Indian Ocean via Suez Canal"),
        ("black_sea", "Location", "Body of water critical for Ukrainian grain exports"),
        ("mediterranean_sea", "Location", "Sea connecting Europe, Africa, and Middle East"),
        ("bay_of_bengal", "Location", "Body of water between India and Southeast Asia"),
        ("arctic_northern_sea_route", "Location", "Emerging shipping route along Russia's Arctic coast"),
        ("mundra_port", "Location", "India's largest commercial port operated by Adani Group in Gujarat"),
        ("nhava_sheva_port", "Location", "Major container port serving Mumbai metropolitan region"),
        ("chennai_port", "Location", "Major port on India's east coast for automotive and container trade"),
        ("visakhapatnam_port", "Location", "Strategic Indian port and naval base on east coast"),
        ("kandla_port", "Location", "Major Indian port in Gujarat for bulk cargo and oil imports"),
        ("cochin_port", "Location", "Kerala port and international container transshipment terminal"),
        ("hambantota_port", "Location", "Sri Lankan port operated by China on 99-year lease"),
        ("port_of_singapore", "Location", "World's second busiest container port and trading hub"),
        ("port_of_shanghai", "Location", "World's busiest container port"),
        ("port_of_rotterdam", "Location", "Europe's largest port and oil refining center"),
        ("port_of_fujairah", "Location", "UAE bunkering hub and alternative to Strait of Hormuz"),
        ("port_of_duqm", "Location", "Omani port developed as India-friendly logistics hub"),
        ("port_of_mombasa", "Location", "Kenya's main port and gateway to East African trade"),
        ("port_of_djibouti", "Location", "Strategic Horn of Africa port with multiple military bases"),
        ("chabahar_shahid_beheshti_terminal", "Location", "India-developed terminal at Chabahar port in Iran"),
        ("bandar_abbas", "Location", "Major Iranian port on the Strait of Hormuz"),
        ("jebel_ali_free_zone", "Location", "Dubai free trade zone hosting 8700+ companies"),
        ("sagarmala_project", "Infrastructure", "India's port-led development program with $120B investment"),
        ("dedicated_freight_corridor", "Infrastructure", "India's two freight rail corridors connecting major ports to hinterland"),
        ("bharatmala_project", "Infrastructure", "India's highway development program connecting economic corridors"),
        ("india_lng_terminals", "Infrastructure", "India's 7 operational LNG regasification terminals"),
        ("east_west_gas_pipeline", "Infrastructure", "India's proposed national gas grid connecting terminals to demand centers"),
        ("tapi_pipeline", "Infrastructure", "Turkmenistan-Afghanistan-Pakistan-India gas pipeline project"),
        ("iran_pakistan_pipeline", "Infrastructure", "Proposed gas pipeline from Iran to Pakistan, facing US sanctions pressure"),
        ("btc_pipeline", "Infrastructure", "Baku-Tbilisi-Ceyhan oil pipeline from Azerbaijan via Georgia to Turkey"),
        ("tanap_pipeline", "Infrastructure", "Trans-Anatolian gas pipeline from Azerbaijan through Turkey to Europe"),
        ("nord_stream_pipeline", "Infrastructure", "Sabotaged undersea gas pipeline from Russia to Germany"),
        ("turkstream_pipeline", "Infrastructure", "Gas pipeline from Russia to Turkey under the Black Sea"),
        ("east_africa_crude_pipeline", "Infrastructure", "Proposed pipeline from Uganda to Tanzania coast"),
        ("china_central_asia_gas_pipeline", "Infrastructure", "Gas pipeline from Turkmenistan to China via Kazakhstan and Uzbekistan"),
        ("china_myanmar_oil_gas_pipeline", "Infrastructure", "Pipeline from Myanmar coast to Kunming in China"),
        ("india_myanmar_thailand_trilateral_highway", "Infrastructure", "Road connecting Northeast India to Thailand via Myanmar"),
        ("kaladan_multi_modal_transit", "Infrastructure", "India-Myanmar transport corridor connecting Kolkata to Mizoram via Sittwe port"),

        # === COMPANIES (expanding beyond CSV) ===
        ("adani_group", "Company", "Indian conglomerate in ports, energy, logistics, and mining"),
        ("adani_ports", "Company", "India's largest private port operator managing Mundra and 13 other ports"),
        ("reliance_jio", "Company", "Indian telecom giant and digital services provider"),
        ("tata_steel", "Company", "Indian steel producer and global steelmaker"),
        ("tata_motors", "Company", "Indian automotive manufacturer including Jaguar Land Rover"),
        ("infosys", "Company", "Indian IT services company and global digital consultancy"),
        ("hcl_tech", "Company", "Indian IT services and technology company"),
        ("mahindra_group", "Company", "Indian conglomerate in auto, defense, IT, and agriculture"),
        ("bajaj_auto", "Company", "Indian two-wheeler and three-wheeler manufacturer"),
        ("bharti_airtel", "Company", "Indian telecom operator with operations across Africa and South Asia"),
        ("hdfc_bank", "Company", "India's largest private sector bank"),
        ("state_bank_of_india", "Company", "India's largest public sector bank"),
        ("lic", "Company", "Life Insurance Corporation of India, largest institutional investor"),
        ("ongc", "Company", "Oil and Natural Gas Corporation of India, largest domestic oil producer"),
        ("iocl", "Company", "India's largest refiner and fuel retailer"),
        ("bharat_petroleum", "Company", "Indian state-owned petroleum refiner and distributor"),
        ("hindustan_petroleum", "Company", "Indian state-owned petroleum company"),
        ("ntpc", "Company", "India's largest power generation company"),
        ("coal_india", "Company", "World's largest coal mining company by production"),
        ("bhel", "Company", "Bharat Heavy Electricals Limited, Indian power equipment manufacturer"),
        ("gail", "Company", "India's largest natural gas processing and distribution company"),
        ("vedanta_resources", "Company", "Indian mining and metals conglomerate"),
        ("jsw_steel", "Company", "Indian steel producer and infrastructure conglomerate"),
        ("hindalco", "Company", "Aditya Birla Group aluminum and copper producer"),
        ("nvidia", "Company", "US semiconductor company leading AI chip design"),
        ("tsmc", "Company", "Taiwan Semiconductor Manufacturing Company, world's largest contract chipmaker"),
        ("samsung_electronics", "Company", "South Korean electronics giant, major semiconductor and display maker"),
        ("asml", "Company", "Dutch company with monopoly on extreme ultraviolet lithography machines"),
        ("intel", "Company", "US semiconductor company investing in domestic manufacturing"),
        ("apple", "Company", "US technology company diversifying supply chain to India and Vietnam"),
        ("foxconn", "Company", "Taiwanese electronics manufacturer with expanding India operations"),
        ("tesla", "Company", "US electric vehicle and clean energy company"),
        ("byd", "Company", "Chinese electric vehicle and battery manufacturer, world's largest EV maker"),
        ("catl", "Company", "Chinese battery manufacturer, world's largest EV battery maker"),
        ("saudi_aramco", "Company", "Saudi state oil company, world's most valuable energy firm"),
        ("total_energies", "Company", "French energy major with LNG and renewable portfolio"),
        ("bp", "Company", "British energy company transitioning from fossil fuels to renewables"),
        ("shell", "Company", "British-Dutch energy major with global LNG operations"),
        ("exxonmobil", "Company", "US largest oil and gas company"),
        ("chevron", "Company", "US oil and gas company with Middle East operations"),
        ("gazprom", "Company", "Russian state gas company, world's largest natural gas producer"),
        ("rosneft", "Company", "Russian state oil company, major crude supplier to India"),
        ("novatek", "Company", "Russian LNG producer operating Arctic LNG 2 project"),
        ("dp_world", "Company", "UAE-based global port operator managing 82 terminals worldwide"),
        ("huawei", "Company", "Chinese tech giant in telecom and 5G infrastructure"),
        ("baidu", "Company", "Chinese AI and internet technology company"),
        ("alibaba", "Company", "Chinese e-commerce and cloud computing giant"),
        ("tencent", "Company", "Chinese technology conglomerate in gaming, social media, fintech"),
        ("amazon_web_services", "Company", "US cloud computing leader with global data center network"),
        ("microsoft", "Company", "US technology company with Azure cloud and AI investments"),
        ("google", "Company", "US technology company with AI, cloud, and Waymo autonomous driving"),
        ("spacex", "Company", "US aerospace company operating Starlink satellite internet constellation"),
        ("boeing", "Company", "US aerospace and defense manufacturer"),
        ("airbus", "Company", "European aerospace and defense manufacturer"),
        ("lockheed_martin", "Company", "US defense contractor manufacturing F-35 and missile defense systems"),
        ("raytheon", "Company", "US defense contractor manufacturing Patriot missile systems"),
        ("northrop_grumman", "Company", "US defense contractor manufacturing B-21 bomber and space systems"),
        ("bae_systems", "Company", "British defense, security, and aerospace company"),
        ("thales", "Company", "French defense electronics and cybersecurity company"),
        ("rafael_advanced_defense", "Company", "Israeli defense company manufacturing Iron Dome and missile systems"),
        ("elbit_systems", "Company", "Israeli defense electronics company"),
        ("bharat_electronics_limited", "Company", "Indian defense electronics manufacturer"),
        ("cochin_shipyard", "Company", "Indian shipbuilder constructing aircraft carrier and naval vessels"),
        ("mazagon_dock", "Company", "Indian shipbuilder constructing submarines and destroyers"),
        ("hal_tejas", "Company", "Program for India's indigenous light combat aircraft"),
    ]
    return nodes


def generate_defense_nodes():
    """Generate defense domain nodes: military assets, bases, weapons."""
    nodes = [
        # === MILITARY BASES & FACILITIES ===
        ("camp_lemonnier", "Location", "US military base in Djibouti, largest permanent US base in Africa"),
        ("diego_garcia", "Location", "US-UK military base in Indian Ocean, strategic bomber and naval hub"),
        ("al_udeid_air_base", "Location", "Largest US military facility in Middle East, located in Qatar"),
        ("camp_arifjan", "Location", "US Army base in Kuwait supporting Middle East operations"),
        ("incirlik_air_base", "Location", "US/NATO air base in Turkey with tactical nuclear weapons"),
        ("ramstein_air_base", "Location", "US Air Force headquarters in Europe, Germany"),
        ("yokosuka_naval_base", "Location", "Largest US naval facility outside the US, in Japan"),
        ("changi_naval_base", "Location", "US Navy logistics hub in Singapore"),
        ("andaman_nicobar_command", "Location", "India's joint military command controlling Malacca Strait approaches"),
        ("india_agalega_base", "Location", "Indian military facility in Mauritius for Indian Ocean surveillance"),
        ("karwar_naval_base", "Location", "India's largest naval base on the west coast, INS Kadamba"),
        ("tartus_naval_base", "Location", "Russian naval facility in Syria, only Mediterranean base"),
        ("cam_ranh_bay", "Location", "Vietnamese naval base with historical Russian access"),
        ("chinese_djibouti_base", "Location", "China's first overseas military base established 2017"),
        ("hainan_naval_base", "Location", "Chinese submarine base in South China Sea"),
        ("pearl_harbor", "Location", "US Pacific Fleet headquarters in Hawaii"),
        ("guam_military_base", "Location", "US strategic military hub in Western Pacific"),
        ("thule_air_base", "Location", "US Space Force early warning radar facility in Greenland"),

        # === WEAPONS & MILITARY SYSTEMS ===
        ("brahmos_missile", "MilitaryAsset", "India-Russia joint venture supersonic cruise missile Mach 2.8"),
        ("s400_missile_system", "MilitaryAsset", "Russian air defense system purchased by India and Turkey"),
        ("iron_dome", "MilitaryAsset", "Israeli short-range air defense system for rocket interception"),
        ("patriot_missile", "MilitaryAsset", "US air defense system deployed globally for missile defense"),
        ("thaad", "MilitaryAsset", "US Terminal High Altitude Area Defense anti-ballistic missile system"),
        ("f35_lightning", "MilitaryAsset", "US fifth-generation stealth multirole fighter aircraft"),
        ("rafale_fighter", "MilitaryAsset", "French fourth-generation fighter aircraft operated by India"),
        ("tejas_lca", "MilitaryAsset", "India's indigenous light combat aircraft"),
        ("ins_vikrant", "MilitaryAsset", "India's first domestically built aircraft carrier commissioned 2022"),
        ("ins_arihant", "MilitaryAsset", "India's nuclear-powered ballistic missile submarine"),
        ("agni_v_missile", "MilitaryAsset", "Indian ICBM with 5500km range for nuclear deterrence"),
        ("k4_slbm", "MilitaryAsset", "Indian submarine-launched ballistic missile for second-strike capability"),
        ("hypersonic_glide_vehicle", "MilitaryAsset", "Advanced weapon system being developed by US, China, Russia, India"),
        ("armed_uav_drones", "MilitaryAsset", "Unmanned aerial vehicles for surveillance and strike operations"),
        ("predator_mq9_drone", "MilitaryAsset", "US MQ-9 Reaper drone being procured by India"),
        ("heron_drone", "MilitaryAsset", "Israeli surveillance drone operated by India"),
        ("pinaka_mlrs", "MilitaryAsset", "Indian multi-barrel rocket launcher system"),
        ("akash_missile", "MilitaryAsset", "Indian surface-to-air missile system for air defense"),
        ("nuclear_submarine", "MilitaryAsset", "Nuclear-powered submarine platform for strategic deterrence"),
        ("aircraft_carrier", "MilitaryAsset", "Large warship serving as seagoing airbase"),
        ("cyber_warfare_capabilities", "MilitaryAsset", "Offensive and defensive capabilities in cyberspace"),
        ("anti_satellite_weapon", "MilitaryAsset", "Weapon capable of destroying satellites, tested by India in 2019"),
        ("ballistic_missile_defense", "MilitaryAsset", "System for intercepting incoming ballistic missiles"),

        # === PERSONS (key geopolitical leaders) ===
        ("narendra_modi", "Person", "Prime Minister of India since 2014, leading BJP government"),
        ("donald_trump", "Person", "President of the United States, returned to office 2025"),
        ("xi_jinping", "Person", "President of China and General Secretary of CPC"),
        ("vladimir_putin", "Person", "President of Russia since 2000 with brief interruption"),
        ("mohammed_bin_salman", "Person", "Crown Prince and Prime Minister of Saudi Arabia, Vision 2030 architect"),
        ("ali_khamenei", "Person", "Supreme Leader of Iran since 1989"),
        ("benjamin_netanyahu", "Person", "Prime Minister of Israel leading coalition government"),
        ("volodymyr_zelenskyy", "Person", "President of Ukraine leading wartime government"),
        ("jaishankar", "Person", "India's External Affairs Minister managing multi-alignment foreign policy"),
        ("ajit_doval", "Person", "India's National Security Advisor coordinating strategic policy"),
        ("jerome_powell", "Person", "Chair of US Federal Reserve managing monetary policy"),
        ("christine_lagarde", "Person", "President of European Central Bank managing eurozone"),
        ("antonio_guterres", "Person", "Secretary-General of the United Nations"),
        ("recep_tayyip_erdogan", "Person", "President of Turkey and NATO member state leader"),
        ("fumio_kishida", "Person", "Former PM of Japan who expanded defense spending to 2% GDP"),
        ("yoon_suk_yeol", "Person", "President of South Korea, expanded defense ties with US and Japan"),
    ]
    return nodes


def generate_technology_nodes():
    """Generate technology domain nodes: tech infrastructure, AI, space, cyber."""
    nodes = [
        # === TECHNOLOGY AREAS ===
        ("artificial_intelligence", "Technology", "Machine learning and AI systems transforming defense, economics, and governance"),
        ("generative_ai", "Technology", "Large language models and AI content generation transforming industries"),
        ("quantum_computing", "Technology", "Next-generation computing paradigm threatening current encryption"),
        ("5g_networks", "Technology", "Fifth generation mobile networks enabling IoT and smart cities"),
        ("6g_research", "Technology", "Sixth generation wireless research for 2030+ deployment"),
        ("blockchain", "Technology", "Distributed ledger technology for cryptocurrencies and supply chain tracking"),
        ("cloud_computing", "Technology", "On-demand computing infrastructure dominated by US and Chinese firms"),
        ("edge_computing", "Technology", "Distributed computing processing data closer to the source"),
        ("internet_of_things", "Technology", "Connected device ecosystem for smart infrastructure"),
        ("autonomous_vehicles", "Technology", "Self-driving vehicle technology for civilian and military applications"),
        ("robotics", "Technology", "Advanced automation technology for manufacturing and defense"),
        ("biotechnology", "Technology", "Biological engineering for medicine, agriculture, and biosecurity"),
        ("crispr_gene_editing", "Technology", "Gene editing technology with medical and agricultural applications"),
        ("mrna_vaccine_technology", "Technology", "Rapid vaccine development platform proven during COVID-19"),
        ("nanotechnology", "Technology", "Manipulation of matter at nanoscale for materials and medicine"),
        ("nuclear_fusion_research", "Technology", "Potential unlimited clean energy source, major breakthroughs in 2020s"),
        ("small_modular_reactors", "Technology", "Next-generation nuclear reactors for distributed power generation"),
        ("euv_lithography", "Technology", "Extreme ultraviolet lithography for sub-7nm semiconductor manufacturing"),
        ("satellite_internet", "Technology", "LEO satellite constellations providing global internet access"),
        ("digital_currency", "Technology", "Central bank digital currencies and cryptocurrencies"),
        ("india_upi", "Technology", "India's Unified Payments Interface processing 10B+ monthly transactions"),
        ("cybersecurity", "Technology", "Protection of digital systems from attacks, critical national security domain"),
        ("additive_manufacturing", "Technology", "3D printing technology for rapid prototyping and distributed manufacturing"),
        ("green_hydrogen_technology", "Technology", "Electrolysis-based hydrogen production using renewable energy"),
        ("carbon_capture_storage", "Technology", "Technology to capture and store CO2 emissions from industrial sources"),
        ("desalination_technology", "Technology", "Converting seawater to freshwater, critical for Middle East and India"),
        ("advanced_battery_technology", "Technology", "Next-gen batteries including solid-state and sodium-ion"),
        ("space_launch_technology", "Technology", "Rocket and satellite launch capabilities for civilian and military use"),
        ("synthetic_biology", "Technology", "Engineering biological systems for industrial and medical purposes"),
        ("precision_agriculture", "Technology", "AI and sensor-driven farming increasing crop yields"),

        # === SPACE ===
        ("chandrayaan_program", "Event", "India's lunar exploration program, Chandrayaan-3 landed on Moon in 2023"),
        ("gaganyaan_program", "Event", "India's human spaceflight program targeting first crewed mission"),
        ("aditya_l1_mission", "Event", "India's first solar observation mission at Lagrange point L1"),
        ("starlink_constellation", "Infrastructure", "SpaceX LEO satellite internet constellation with 5000+ satellites"),
        ("oneweb_constellation", "Infrastructure", "Bharti-backed LEO satellite internet constellation"),
        ("beidou_navigation", "Infrastructure", "China's global satellite navigation system alternative to GPS"),
        ("navic", "Infrastructure", "India's regional satellite navigation system covering India and 1500km beyond"),
        ("galileo_navigation", "Infrastructure", "EU's global satellite navigation system"),
        ("international_space_station", "Infrastructure", "Multinational space station approaching end of life"),
        ("tiangong_space_station", "Infrastructure", "China's modular space station operational since 2022"),

        # === DIGITAL INFRASTRUCTURE ===
        ("india_digital_public_infrastructure", "Infrastructure", "India Stack: Aadhaar + UPI + DigiLocker framework"),
        ("undersea_cable_networks", "Infrastructure", "Global fiber optic cables carrying 95% of intercontinental data"),
        ("india_5g_rollout", "Infrastructure", "India's nationwide 5G deployment by Jio and Airtel"),
        ("semiconductor_fabs_india", "Infrastructure", "Planned semiconductor fabrication facilities in India"),
        ("data_center_parks_india", "Infrastructure", "Growing data center capacity in Mumbai, Chennai, Hyderabad"),
    ]
    return nodes


def generate_climate_nodes():
    """Generate climate and energy domain nodes."""
    nodes = [
        # === RENEWABLE ENERGY ===
        ("solar_energy", "Resource", "Photovoltaic and concentrated solar power generation"),
        ("wind_energy", "Resource", "Onshore and offshore wind power generation"),
        ("hydropower", "Resource", "Electricity generation from flowing water, India 5th largest globally"),
        ("nuclear_energy", "Resource", "Nuclear fission power generation, India operating 22 reactors"),
        ("geothermal_energy", "Resource", "Heat energy from Earth's interior for power generation"),
        ("biofuels", "Resource", "Renewable fuels from biological sources, India's ethanol blending program"),
        ("green_hydrogen", "Resource", "Hydrogen produced from renewable energy via electrolysis"),
        ("blue_hydrogen", "Resource", "Hydrogen from natural gas with carbon capture"),

        # === CLIMATE PHENOMENA ===
        ("global_warming", "Event", "Rising global temperatures due to greenhouse gas emissions"),
        ("sea_level_rise", "Event", "Rising ocean levels threatening coastal cities and island nations"),
        ("arctic_ice_melt", "Event", "Rapid decline of Arctic sea ice opening new shipping routes"),
        ("amazon_deforestation", "Event", "Loss of Amazon rainforest reducing global carbon absorption"),
        ("coral_reef_bleaching", "Event", "Mass bleaching of coral reefs due to ocean warming"),
        ("extreme_weather_events", "Event", "Increasing frequency of hurricanes, floods, droughts, and heatwaves"),
        ("india_monsoon_disruption", "Event", "Changing monsoon patterns affecting Indian agriculture and water supply"),
        ("water_scarcity_crisis", "Event", "Growing freshwater shortage affecting agriculture and urban areas globally"),
        ("el_nino", "Event", "Pacific Ocean warming pattern disrupting global weather and crop yields"),
        ("la_nina", "Event", "Pacific Ocean cooling pattern affecting monsoons and agriculture"),
        ("permafrost_thaw", "Event", "Melting of permafrost releasing methane in Arctic regions"),
        ("sahel_desertification", "Event", "Expansion of desert in sub-Saharan Africa threatening food security"),
        ("glacial_retreat_himalayas", "Event", "Melting Himalayan glaciers threatening water supply for 2 billion people"),
        ("chennai_water_crisis", "Event", "Recurring water shortage in India's fourth largest city"),
        ("delhi_air_pollution", "Event", "Severe air quality crisis in India's capital region"),
        ("india_heatwaves", "Event", "Increasing frequency and severity of heatwaves in India"),

        # === CLIMATE INFRASTRUCTURE ===
        ("india_solar_parks", "Infrastructure", "India's large-scale solar installations including Bhadla Solar Park"),
        ("india_offshore_wind", "Infrastructure", "Planned offshore wind farms in Gujarat and Tamil Nadu"),
        ("india_nuclear_fleet", "Infrastructure", "India's 22 operational nuclear reactors across 7 sites"),
        ("three_gorges_dam", "Infrastructure", "World's largest hydroelectric dam in China"),
        ("narmada_dam_project", "Infrastructure", "India's large dam project providing irrigation and hydropower"),
        ("india_ethanol_blending", "Infrastructure", "India's program targeting 20% ethanol in petrol by 2025"),
        ("india_ev_charging_network", "Infrastructure", "Emerging electric vehicle charging infrastructure across India"),
        ("india_smart_grid", "Infrastructure", "Modernization of India's power transmission and distribution"),
        ("international_solar_alliance", "Organization", "India-led alliance of 120+ nations promoting solar energy"),
        ("global_methane_pledge", "Policy", "Pledge by 150+ countries to reduce methane emissions 30% by 2030"),
        ("india_lng_import_terminals", "Infrastructure", "India's expanding LNG regasification capacity"),
        ("india_strategic_petroleum_reserve", "Infrastructure", "India's underground crude oil reserves at Visakhapatnam, Mangalore, Padur"),
        ("carbon_credit_market", "Indicator", "Global market for carbon emission permits and offsets"),
        ("india_renewable_target", "Policy", "India's target of 500 GW renewable energy capacity by 2030"),
        ("india_net_zero_2070", "Policy", "India's commitment to net zero emissions by 2070"),
        ("global_climate_finance", "Indicator", "International funding for climate change adaptation and mitigation"),
    ]
    return nodes


def generate_society_nodes():
    """Generate society domain nodes: demographics, migration, health, education."""
    nodes = [
        # === DEMOGRAPHICS & MIGRATION ===
        ("india_population", "Indicator", "India's population surpassed 1.44 billion making it world's most populous nation"),
        ("india_median_age", "Indicator", "India's median age of 28 years providing demographic dividend"),
        ("india_urbanization_rate", "Indicator", "Rapid urbanization with 35% urban population growing annually"),
        ("indian_diaspora_gcc", "Indicator", "8.5 million Indian workers in Gulf states sending $50B+ annual remittances"),
        ("indian_diaspora_usa", "Indicator", "4.4 million Indian Americans contributing to tech and business sectors"),
        ("indian_diaspora_uk", "Indicator", "1.6 million Indian-origin population in United Kingdom"),
        ("global_refugee_crisis", "Event", "Record 110 million displaced people worldwide in 2023"),
        ("india_internal_migration", "Event", "Large-scale rural to urban migration transforming Indian economy"),
        ("climate_migration", "Event", "Displacement of populations due to climate change impacts"),
        ("brain_drain_reversal_india", "Event", "Increasing return of skilled Indians from abroad"),
        ("labor_shortage_gcc", "Event", "Gulf states diversifying workforce away from expatriate dependency"),

        # === HEALTH ===
        ("india_healthcare_system", "Infrastructure", "India's expanding but strained public and private healthcare network"),
        ("ayushman_bharat", "Policy", "India's national health insurance scheme covering 500 million beneficiaries"),
        ("india_vaccine_manufacturing", "Infrastructure", "India producing 60% of world's vaccines via Serum Institute and others"),
        ("serum_institute_of_india", "Company", "World's largest vaccine manufacturer by doses produced"),
        ("biocon", "Company", "Indian biotechnology company and biosimilar manufacturer"),
        ("dr_reddys_laboratories", "Company", "Indian pharmaceutical company with global generic drug operations"),
        ("cipla", "Company", "Indian pharmaceutical company focusing on respiratory and anti-retroviral drugs"),
        ("global_pandemic_preparedness", "Event", "International coordination for future pandemic prevention"),
        ("antimicrobial_resistance", "Event", "Growing global threat of antibiotic-resistant bacteria"),
        ("india_digital_health_mission", "Policy", "National initiative for digital health IDs and records"),

        # === EDUCATION & RESEARCH ===
        ("india_iit_system", "Organization", "Indian Institutes of Technology producing global tech leaders"),
        ("india_iim_system", "Organization", "Indian Institutes of Management training business leaders"),
        ("india_new_education_policy", "Policy", "NEP 2020 reforming India's education system"),
        ("india_research_spending", "Indicator", "India's R&D spending at 0.7% of GDP, target to reach 2%"),
        ("global_ai_talent_pool", "Indicator", "Distribution of AI researchers and engineers worldwide"),
        ("india_stem_graduates", "Indicator", "India producing 2.6 million STEM graduates annually"),
        ("india_startup_ecosystem", "Indicator", "India's third largest startup ecosystem with 100+ unicorns"),

        # === CULTURAL & SOCIAL ===
        ("india_soft_power", "Indicator", "India's global cultural influence through film, yoga, cuisine, diaspora"),
        ("bollywood_industry", "Company", "Indian film industry producing 1500+ films annually"),
        ("india_g20_presidency_2023", "Event", "India's presidency of G20 in 2023 elevating global positioning"),
        ("india_un_security_council_bid", "Event", "India's campaign for permanent UNSC membership"),
        ("digital_divide", "Event", "Growing gap between digital haves and have-nots within and between nations"),
        ("india_women_labor_participation", "Indicator", "Indian women's workforce participation rate at ~37%"),
        ("global_food_security", "Indicator", "International food availability and access metrics"),
        ("india_poverty_rate", "Indicator", "India's multidimensional poverty declining to under 12%"),
    ]
    return nodes


# ═══════════════════════════════════════════════════════════════════
# EDGES: Comprehensive relationships across all domains
# ═══════════════════════════════════════════════════════════════════

def generate_geopolitics_edges():
    """Cross-domain geopolitics edges."""
    return [
        # === Alliances & Memberships ===
        ("india", "quad", "MEMBER_OF", 0.99),
        ("usa", "quad", "MEMBER_OF", 0.99),
        ("japan", "quad", "MEMBER_OF", 0.99),
        ("australia", "quad", "MEMBER_OF", 0.99),
        ("usa", "nato", "MEMBER_OF", 0.99),
        ("uk", "nato", "MEMBER_OF", 0.99),
        ("france", "nato", "MEMBER_OF", 0.99),
        ("germany", "nato", "MEMBER_OF", 0.99),
        ("turkey", "nato", "MEMBER_OF", 0.99),
        ("poland", "nato", "MEMBER_OF", 0.99),
        ("finland", "nato", "MEMBER_OF", 0.99),
        ("sweden", "nato", "MEMBER_OF", 0.99),
        ("india", "brics", "MEMBER_OF", 0.99),
        ("china", "brics", "MEMBER_OF", 0.99),
        ("russia", "brics", "MEMBER_OF", 0.99),
        ("brazil", "brics", "MEMBER_OF", 0.99),
        ("south_africa", "brics", "MEMBER_OF", 0.99),
        ("uae", "brics", "MEMBER_OF", 0.97),
        ("iran", "brics", "MEMBER_OF", 0.97),
        ("egypt", "brics", "MEMBER_OF", 0.97),
        ("ethiopia", "brics", "MEMBER_OF", 0.97),
        ("saudi_arabia", "brics", "MEMBER_OF", 0.97),
        ("india", "sco", "MEMBER_OF", 0.99),
        ("china", "sco", "MEMBER_OF", 0.99),
        ("russia", "sco", "MEMBER_OF", 0.99),
        ("pakistan", "sco", "MEMBER_OF", 0.99),
        ("iran", "sco", "MEMBER_OF", 0.97),
        ("india", "g20", "MEMBER_OF", 0.99),
        ("china", "g20", "MEMBER_OF", 0.99),
        ("usa", "g20", "MEMBER_OF", 0.99),
        ("saudi_arabia", "gcc", "MEMBER_OF", 0.99),
        ("uae", "gcc", "MEMBER_OF", 0.99),
        ("qatar", "gcc", "MEMBER_OF", 0.99),
        ("kuwait", "gcc", "MEMBER_OF", 0.99),
        ("bahrain", "gcc", "MEMBER_OF", 0.99),
        ("oman", "gcc", "MEMBER_OF", 0.99),
        ("indonesia", "asean", "MEMBER_OF", 0.99),
        ("malaysia", "asean", "MEMBER_OF", 0.99),
        ("singapore", "asean", "MEMBER_OF", 0.99),
        ("thailand", "asean", "MEMBER_OF", 0.99),
        ("vietnam", "asean", "MEMBER_OF", 0.99),
        ("philippines", "asean", "MEMBER_OF", 0.99),
        ("myanmar", "asean", "MEMBER_OF", 0.99),
        ("iran", "opec", "MEMBER_OF", 0.99),
        ("saudi_arabia", "opec", "MEMBER_OF", 0.99),
        ("uae", "opec", "MEMBER_OF", 0.99),
        ("iraq", "opec", "MEMBER_OF", 0.99),
        ("kuwait", "opec", "MEMBER_OF", 0.99),
        ("nigeria", "opec", "MEMBER_OF", 0.99),
        ("venezuela", "opec", "MEMBER_OF", 0.99),
        ("algeria", "opec", "MEMBER_OF", 0.99),
        ("libya", "opec", "MEMBER_OF", 0.99),
        ("russia", "opec_plus", "MEMBER_OF", 0.99),
        ("australia", "aukus", "MEMBER_OF", 0.99),
        ("uk", "aukus", "MEMBER_OF", 0.99),
        ("usa", "aukus", "MEMBER_OF", 0.99),
        ("usa", "five_eyes", "MEMBER_OF", 0.99),
        ("uk", "five_eyes", "MEMBER_OF", 0.99),
        ("canada", "five_eyes", "MEMBER_OF", 0.99),
        ("australia", "five_eyes", "MEMBER_OF", 0.99),
        ("new_zealand", "five_eyes", "MEMBER_OF", 0.99),

        # === Conflicts & Tensions ===
        ("russia", "ukraine", "CONFLICT_WITH", 0.99),
        ("china", "taiwan", "THREATENS", 0.95),
        ("israel", "hamas", "CONFLICT_WITH", 0.99),
        ("israel", "hezbollah", "CONFLICT_WITH", 0.98),
        ("iran", "hezbollah", "FUNDS", 0.97),
        ("iran", "hamas", "FUNDS", 0.95),
        ("iran", "houthis", "FUNDS", 0.97),
        ("north_korea", "south_korea", "THREATENS", 0.95),
        ("north_korea", "iran", "COOPERATES_WITH", 0.90),
        ("china", "philippines", "CONFLICT_WITH", 0.88),
        ("india", "china", "COMPETES_WITH", 0.92),
        ("india", "pakistan", "CONFLICT_WITH", 0.90),
        ("usa", "china", "COMPETES_WITH", 0.95),

        # === Strategic partnerships ===
        ("india", "france", "PARTNERS_WITH", 0.95),
        ("india", "japan", "PARTNERS_WITH", 0.96),
        ("india", "australia", "PARTNERS_WITH", 0.94),
        ("india", "uae", "PARTNERS_WITH", 0.95),
        ("india", "saudi_arabia", "PARTNERS_WITH", 0.93),
        ("india", "russia", "PARTNERS_WITH", 0.90),
        ("china", "russia", "ALLIES_WITH", 0.93),
        ("china", "pakistan", "ALLIES_WITH", 0.95),
        ("usa", "israel", "ALLIES_WITH", 0.99),
        ("usa", "japan", "ALLIES_WITH", 0.99),
        ("usa", "south_korea", "ALLIES_WITH", 0.98),
        ("usa", "uk", "ALLIES_WITH", 0.99),
        ("usa", "saudi_arabia", "ALLIES_WITH", 0.92),
        ("turkey", "azerbaijan", "ALLIES_WITH", 0.95),

        # === Borders ===
        ("india", "pakistan", "BORDERS", 0.99),
        ("india", "china", "BORDERS", 0.99),
        ("india", "nepal", "BORDERS", 0.99),
        ("india", "bhutan", "BORDERS", 0.99),
        ("india", "bangladesh", "BORDERS", 0.99),
        ("india", "myanmar", "BORDERS", 0.99),
        ("iran", "iraq", "BORDERS", 0.99),
        ("iran", "afghanistan", "BORDERS", 0.99),
        ("iran", "pakistan", "BORDERS", 0.99),
        ("iran", "turkey", "BORDERS", 0.99),
        ("russia", "ukraine", "BORDERS", 0.99),
        ("russia", "china", "BORDERS", 0.99),
        ("russia", "finland", "BORDERS", 0.99),
        ("china", "north_korea", "BORDERS", 0.99),
        ("china", "vietnam", "BORDERS", 0.99),
        ("china", "myanmar", "BORDERS", 0.99),
        ("china", "mongolia", "BORDERS", 0.99),
        ("egypt", "libya", "BORDERS", 0.99),
        ("egypt", "sudan", "BORDERS", 0.99),

        # === Keys persons → countries leading ===
        ("narendra_modi", "india", "LEADS", 0.99),
        ("donald_trump", "usa", "LEADS", 0.99),
        ("xi_jinping", "china", "LEADS", 0.99),
        ("vladimir_putin", "russia", "LEADS", 0.99),
        ("mohammed_bin_salman", "saudi_arabia", "LEADS", 0.99),
        ("ali_khamenei", "iran", "LEADS", 0.99),
        ("benjamin_netanyahu", "israel", "LEADS", 0.99),
        ("volodymyr_zelenskyy", "ukraine", "LEADS", 0.99),
        ("recep_tayyip_erdogan", "turkey", "LEADS", 0.99),

        # === Sanctions & pressure ===
        ("usa", "iran", "SANCTIONS", 0.99),
        ("usa", "russia", "SANCTIONS", 0.98),
        ("usa", "north_korea", "SANCTIONS", 0.99),
        ("usa", "venezuela", "SANCTIONS", 0.97),
        ("usa", "syria", "SANCTIONS", 0.98),
        ("european_union", "russia", "SANCTIONS", 0.98),
        ("european_union", "iran", "SANCTIONS", 0.95),
        ("usa", "china", "SANCTIONS", 0.90),

        # === BRI & corridor competition ===
        ("china", "bri", "LEADS", 0.99),
        ("china", "gwadar_port", "INVESTS_IN", 0.98),
        ("china", "hambantota_port", "CONTROLS", 0.97),
        ("china", "chinese_djibouti_base", "OPERATES", 0.99),
        ("india", "chabahar_port", "INVESTS_IN", 0.98),
        ("india", "sagarmala_project", "DEVELOPS", 0.99),
        ("india", "andaman_nicobar_command", "OPERATES", 0.99),
        ("india", "india_agalega_base", "DEVELOPS", 0.96),

        # === Events → impacts ===
        ("russia_ukraine_war", "oil_price", "INCREASES", 0.97),
        ("russia_ukraine_war", "global_food_price_index", "INCREASES", 0.96),
        ("russia_ukraine_war", "freight_costs", "INCREASES", 0.95),
        ("red_sea_crisis", "freight_costs", "INCREASES", 0.98),
        ("red_sea_crisis", "shipping_insurance_rates", "INCREASES", 0.98),
        ("taiwan_strait_tensions", "semiconductors", "THREATENS", 0.93),
        ("gaza_conflict_2023", "oil_price", "INCREASES", 0.88),
        ("2026_iran_conflict", "global_trade_volume", "DISRUPTS", 0.94),
        ("2026_iran_conflict", "shipping_insurance_rates", "INCREASES", 0.98),
    ]


def generate_economics_edges():
    """Cross-domain economics edges."""
    return [
        # === India imports ===
        ("india", "coal", "IMPORTS", 0.99),
        ("india", "gold", "IMPORTS", 0.98),
        ("india", "palm_oil", "IMPORTS", 0.99),
        ("india", "natural_gas", "IMPORTS", 0.98),
        ("india", "iron_ore", "IMPORTS", 0.85),
        ("india", "copper", "IMPORTS", 0.92),
        ("india", "potash", "IMPORTS", 0.95),
        ("india", "semiconductors", "IMPORTS", 0.97),
        ("india", "solar_panels", "IMPORTS", 0.96),
        ("india", "ev_batteries", "IMPORTS", 0.93),

        # === India exports ===
        ("india", "rice", "EXPORTS", 0.99),
        ("india", "tea", "EXPORTS", 0.99),
        ("india", "cotton", "EXPORTS", 0.95),
        ("india", "steel", "EXPORTS", 0.93),
        ("india", "sugar", "EXPORTS", 0.92),
        ("india", "pharmaceuticals", "EXPORTS", 0.99),

        # === Global commodity producers ===
        ("saudi_arabia", "crude_oil", "PRODUCES", 0.99),
        ("russia", "crude_oil", "PRODUCES", 0.99),
        ("iran", "crude_oil", "PRODUCES", 0.99),
        ("iraq", "crude_oil", "PRODUCES", 0.99),
        ("uae", "crude_oil", "PRODUCES", 0.99),
        ("qatar", "lng", "PRODUCES", 0.99),
        ("australia", "lng", "PRODUCES", 0.98),
        ("usa", "lng", "PRODUCES", 0.98),
        ("russia", "natural_gas", "PRODUCES", 0.99),
        ("norway", "natural_gas", "PRODUCES", 0.98),
        ("algeria", "natural_gas", "PRODUCES", 0.97),
        ("australia", "iron_ore", "PRODUCES", 0.99),
        ("brazil", "iron_ore", "PRODUCES", 0.99),
        ("india", "iron_ore", "PRODUCES", 0.95),
        ("chile", "copper", "PRODUCES", 0.99),
        ("democratic_republic_of_congo", "cobalt", "PRODUCES", 0.99),
        ("australia", "lithium", "PRODUCES", 0.98),
        ("chile", "lithium", "PRODUCES", 0.98),
        ("argentina", "lithium", "PRODUCES", 0.96),
        ("china", "rare_earth_elements", "PRODUCES", 0.99),
        ("indonesia", "nickel", "PRODUCES", 0.99),
        ("south_africa", "platinum_group_metals", "PRODUCES", 0.99),
        ("china", "steel", "PRODUCES", 0.99),
        ("india", "steel", "PRODUCES", 0.98),
        ("india", "wheat", "PRODUCES", 0.99),
        ("china", "wheat", "PRODUCES", 0.99),
        ("india", "rice", "PRODUCES", 0.99),
        ("thailand", "rice", "PRODUCES", 0.98),
        ("malaysia", "palm_oil", "PRODUCES", 0.99),
        ("indonesia", "palm_oil", "PRODUCES", 0.99),
        ("india", "sugar", "PRODUCES", 0.99),
        ("brazil", "sugar", "PRODUCES", 0.99),
        ("morocco", "phosphate", "PRODUCES", 0.99),
        ("kazakhstan", "uranium", "PRODUCES", 0.99),
        ("canada", "potash", "PRODUCES", 0.99),
        ("taiwan", "semiconductors", "PRODUCES", 0.99),
        ("south_korea", "semiconductors", "PRODUCES", 0.98),
        ("china", "solar_panels", "PRODUCES", 0.99),
        ("china", "ev_batteries", "PRODUCES", 0.99),

        # === Chokepoint dependencies ===
        ("strait_of_malacca", "crude_oil", "TRANSPORT_ROUTE_FOR", 0.99),
        ("strait_of_malacca", "lng", "TRANSPORT_ROUTE_FOR", 0.98),
        ("suez_canal", "crude_oil", "TRANSPORT_ROUTE_FOR", 0.97),
        ("bosphorus_strait", "crude_oil", "TRANSPORT_ROUTE_FOR", 0.95),
        ("panama_canal", "lng", "TRANSPORT_ROUTE_FOR", 0.90),
        ("persian_gulf", "crude_oil", "FACILITATES_TRADE_OF", 0.99),
        ("red_sea", "crude_oil", "TRANSPORT_ROUTE_FOR", 0.96),

        # === Company operations ===
        ("adani_ports", "mundra_port", "OPERATES", 0.99),
        ("dp_world", "jebel_ali_port", "OPERATES", 0.99),
        ("dp_world", "nhava_sheva_port", "OPERATES", 0.95),
        ("saudi_aramco", "crude_oil", "PRODUCES", 0.99),
        ("gazprom", "natural_gas", "PRODUCES", 0.99),
        ("rosneft", "crude_oil", "PRODUCES", 0.99),
        ("ongc", "crude_oil", "PRODUCES", 0.95),
        ("reliance_industries", "crude_oil", "IMPORTS", 0.97),
        ("iocl", "crude_oil", "IMPORTS", 0.98),
        ("bharat_petroleum", "crude_oil", "IMPORTS", 0.97),
        ("hindustan_petroleum", "crude_oil", "IMPORTS", 0.96),
        ("coal_india", "coal", "PRODUCES", 0.99),
        ("gail", "natural_gas", "IMPORTS", 0.97),
        ("ntpc", "coal", "IMPORTS", 0.97),
        ("tata_steel", "steel", "PRODUCES", 0.99),
        ("jsw_steel", "steel", "PRODUCES", 0.98),
        ("vedanta_resources", "aluminum", "PRODUCES", 0.96),
        ("hindalco", "aluminum", "PRODUCES", 0.97),
        ("nvidia", "semiconductors", "MANUFACTURES", 0.99),
        ("tsmc", "semiconductors", "MANUFACTURES", 0.99),
        ("samsung_electronics", "semiconductors", "MANUFACTURES", 0.99),
        ("asml", "euv_lithography", "MANUFACTURES", 0.99),
        ("intel", "semiconductors", "MANUFACTURES", 0.98),
        ("byd", "ev_batteries", "MANUFACTURES", 0.99),
        ("catl", "ev_batteries", "MANUFACTURES", 0.99),
        ("tesla", "autonomous_vehicles", "DEVELOPS", 0.97),

        # === HQ locations ===
        ("adani_group", "india", "HEADQUARTERED_IN", 0.99),
        ("reliance_industries", "india", "HEADQUARTERED_IN", 0.99),
        ("tata_steel", "india", "HEADQUARTERED_IN", 0.99),
        ("infosys", "india", "HEADQUARTERED_IN", 0.99),
        ("tcs", "india", "HEADQUARTERED_IN", 0.99),
        ("wipro", "india", "HEADQUARTERED_IN", 0.99),
        ("nvidia", "usa", "HEADQUARTERED_IN", 0.99),
        ("tsmc", "taiwan", "HEADQUARTERED_IN", 0.99),
        ("samsung_electronics", "south_korea", "HEADQUARTERED_IN", 0.99),
        ("asml", "netherlands", "HEADQUARTERED_IN", 0.99),
        ("saudi_aramco", "saudi_arabia", "HEADQUARTERED_IN", 0.99),
        ("gazprom", "russia", "HEADQUARTERED_IN", 0.99),
        ("dp_world", "uae", "HEADQUARTERED_IN", 0.99),
        ("huawei", "china", "HEADQUARTERED_IN", 0.99),
        ("spacex", "usa", "HEADQUARTERED_IN", 0.99),
        ("lockheed_martin", "usa", "HEADQUARTERED_IN", 0.99),
        ("boeing", "usa", "HEADQUARTERED_IN", 0.99),
        ("airbus", "france", "HEADQUARTERED_IN", 0.99),
        ("bp", "uk", "HEADQUARTERED_IN", 0.99),
        ("shell", "uk", "HEADQUARTERED_IN", 0.99),
        ("total_energies", "france", "HEADQUARTERED_IN", 0.99),

        # === Economic indicators → impacts ===
        ("brent_crude_price", "india_inflation", "AFFECTS", 0.97),
        ("brent_crude_price", "india_current_account_deficit", "AFFECTS", 0.96),
        ("brent_crude_price", "indian_rupee_exchange_rate", "AFFECTS", 0.95),
        ("us_federal_funds_rate", "india_fdi_inflows", "AFFECTS", 0.90),
        ("us_federal_funds_rate", "indian_rupee_exchange_rate", "AFFECTS", 0.92),
        ("oil_price", "brent_crude_price", "AFFECTS", 0.99),
        ("global_food_price_index", "india_cpi", "AFFECTS", 0.92),
        ("freight_costs", "india_inflation", "AFFECTS", 0.88),
        ("india_forex_reserves", "indian_rupee_exchange_rate", "AFFECTS", 0.93),

        # === Indian corridors ===
        ("india", "imec", "PARTICIPATES_IN", 0.97),
        ("india", "instc", "PARTICIPATES_IN", 0.98),
        ("india", "dedicated_freight_corridor", "DEVELOPS", 0.99),
        ("india", "bharatmala_project", "DEVELOPS", 0.99),
        ("india", "sagarmala_project", "DEVELOPS", 0.99),
        ("india", "india_myanmar_thailand_trilateral_highway", "DEVELOPS", 0.95),

        # === Trade agreements ===
        ("india", "india_uae_cepa", "SIGNS", 0.99),
        ("uae", "india_uae_cepa", "SIGNS", 0.99),
        ("india", "india_australia_ecta", "SIGNS", 0.99),
        ("australia", "india_australia_ecta", "SIGNS", 0.99),
        ("india", "rcep", "AFFECTS", 0.85),
    ]


def generate_defense_edges():
    """Cross-domain defense edges."""
    return [
        # === Defense partnerships ===
        ("india", "usa", "DEFENSE_PARTNERSHIP_WITH", 0.96),
        ("india", "israel", "DEFENSE_PARTNERSHIP_WITH", 0.97),
        ("india", "france", "DEFENSE_PARTNERSHIP_WITH", 0.96),
        ("india", "russia", "DEFENSE_PARTNERSHIP_WITH", 0.94),
        ("india", "japan", "DEFENSE_PARTNERSHIP_WITH", 0.92),
        ("usa", "japan", "DEFENSE_PARTNERSHIP_WITH", 0.99),
        ("usa", "south_korea", "DEFENSE_PARTNERSHIP_WITH", 0.98),
        ("usa", "australia", "DEFENSE_PARTNERSHIP_WITH", 0.99),
        ("usa", "uk", "DEFENSE_PARTNERSHIP_WITH", 0.99),
        ("china", "pakistan", "DEFENSE_PARTNERSHIP_WITH", 0.95),
        ("russia", "india", "SUPPLIES", 0.96),
        ("france", "india", "SUPPLIES", 0.94),
        ("usa", "india", "SUPPLIES", 0.90),
        ("israel", "india", "SUPPLIES", 0.95),

        # === Military deployments ===
        ("usa", "al_udeid_air_base", "OPERATES", 0.99),
        ("usa", "camp_lemonnier", "OPERATES", 0.99),
        ("usa", "camp_arifjan", "OPERATES", 0.99),
        ("usa", "diego_garcia", "OPERATES", 0.99),
        ("usa", "incirlik_air_base", "OPERATES", 0.99),
        ("usa", "ramstein_air_base", "OPERATES", 0.99),
        ("usa", "yokosuka_naval_base", "OPERATES", 0.99),
        ("usa", "guam_military_base", "OPERATES", 0.99),
        ("india", "andaman_nicobar_command", "OPERATES", 0.99),
        ("india", "karwar_naval_base", "OPERATES", 0.99),
        ("russia", "tartus_naval_base", "OPERATES", 0.99),
        ("china", "chinese_djibouti_base", "OPERATES", 0.99),
        ("china", "hainan_naval_base", "OPERATES", 0.99),
        ("us_centcom", "persian_gulf", "OPERATES_IN", 0.99),
        ("us_indopacom", "indian_ocean", "OPERATES_IN", 0.99),
        ("indian_navy", "indian_ocean", "OPERATES_IN", 0.99),
        ("pla_navy", "south_china_sea", "OPERATES_IN", 0.99),

        # === Weapons → countries ===
        ("india", "brahmos_missile", "DEVELOPS", 0.99),
        ("russia", "brahmos_missile", "DEVELOPS", 0.99),
        ("india", "s400_missile_system", "IMPORTS", 0.98),
        ("russia", "s400_missile_system", "EXPORTS", 0.98),
        ("india", "rafale_fighter", "IMPORTS", 0.99),
        ("france", "rafale_fighter", "EXPORTS", 0.99),
        ("india", "tejas_lca", "DEVELOPS", 0.99),
        ("hindustan_aeronautics_limited", "tejas_lca", "MANUFACTURES", 0.99),
        ("india", "ins_vikrant", "DEVELOPS", 0.99),
        ("cochin_shipyard", "ins_vikrant", "MANUFACTURES", 0.99),
        ("india", "ins_arihant", "DEVELOPS", 0.99),
        ("india", "agni_v_missile", "DEVELOPS", 0.99),
        ("india", "predator_mq9_drone", "IMPORTS", 0.95),
        ("usa", "predator_mq9_drone", "EXPORTS", 0.95),
        ("india", "heron_drone", "IMPORTS", 0.97),
        ("israel", "heron_drone", "EXPORTS", 0.97),
        ("israel", "iron_dome", "DEVELOPS", 0.99),
        ("rafael_advanced_defense", "iron_dome", "MANUFACTURES", 0.99),
        ("usa", "f35_lightning", "DEVELOPS", 0.99),
        ("lockheed_martin", "f35_lightning", "MANUFACTURES", 0.99),
        ("usa", "patriot_missile", "DEVELOPS", 0.99),
        ("raytheon", "patriot_missile", "MANUFACTURES", 0.99),
        ("usa", "thaad", "DEVELOPS", 0.99),
        ("india", "anti_satellite_weapon", "DEVELOPS", 0.97),
        ("bharat_electronics_limited", "india", "SUPPLIES", 0.97),
        ("mazagon_dock", "nuclear_submarine", "MANUFACTURES", 0.96),
        ("india", "ballistic_missile_defense", "DEVELOPS", 0.95),

        # === Defense companies → countries ===
        ("lockheed_martin", "usa", "HEADQUARTERED_IN", 0.99),
        ("raytheon", "usa", "HEADQUARTERED_IN", 0.99),
        ("northrop_grumman", "usa", "HEADQUARTERED_IN", 0.99),
        ("bae_systems", "uk", "HEADQUARTERED_IN", 0.99),
        ("thales", "france", "HEADQUARTERED_IN", 0.99),
        ("rafael_advanced_defense", "israel", "HEADQUARTERED_IN", 0.99),
        ("elbit_systems", "israel", "HEADQUARTERED_IN", 0.99),
        ("hindustan_aeronautics_limited", "india", "HEADQUARTERED_IN", 0.99),
        ("bharat_electronics_limited", "india", "HEADQUARTERED_IN", 0.99),
        ("cochin_shipyard", "india", "HEADQUARTERED_IN", 0.99),
        ("mazagon_dock", "india", "HEADQUARTERED_IN", 0.99),

        # === Nuclear capabilities ===
        ("india", "nuclear_energy", "PRODUCES", 0.97),
        ("usa", "nuclear_energy", "PRODUCES", 0.99),
        ("france", "nuclear_energy", "PRODUCES", 0.99),
        ("china", "nuclear_energy", "PRODUCES", 0.99),
        ("russia", "nuclear_energy", "PRODUCES", 0.99),

        # === Indian defense policies ===
        ("india", "make_in_india", "SIGNS", 0.99),
        ("india", "atmanirbhar_bharat", "SIGNS", 0.99),
        ("india", "india_defense_procurement_policy", "SIGNS", 0.99),
    ]


def generate_technology_edges():
    """Cross-domain technology edges."""
    return [
        # === AI leadership ===
        ("usa", "artificial_intelligence", "LEADS", 0.97),
        ("china", "artificial_intelligence", "DEVELOPS", 0.96),
        ("india", "artificial_intelligence", "DEVELOPS", 0.88),
        ("nvidia", "artificial_intelligence", "DEVELOPS", 0.99),
        ("google", "generative_ai", "DEVELOPS", 0.99),
        ("microsoft", "generative_ai", "DEVELOPS", 0.99),
        ("baidu", "generative_ai", "DEVELOPS", 0.95),

        # === Semiconductor supply chain ===
        ("tsmc", "apple", "SUPPLIES", 0.99),
        ("tsmc", "nvidia", "SUPPLIES", 0.99),
        ("asml", "tsmc", "SUPPLIES", 0.99),
        ("asml", "samsung_electronics", "SUPPLIES", 0.99),
        ("asml", "intel", "SUPPLIES", 0.99),
        ("usa", "us_chips_act", "SIGNS", 0.99),
        ("us_chips_act", "semiconductors", "AFFECTS", 0.97),
        ("china", "china_made_in_china_2025", "SIGNS", 0.99),
        ("china_made_in_china_2025", "semiconductors", "AFFECTS", 0.95),
        ("usa", "china", "SANCTIONS", 0.93),
        ("netherlands", "china", "SANCTIONS", 0.90),
        ("japan", "china", "SANCTIONS", 0.88),

        # === Space programs ===
        ("india", "chandrayaan_program", "DEVELOPS", 0.99),
        ("isro", "chandrayaan_program", "DEVELOPS", 0.99),
        ("india", "gaganyaan_program", "DEVELOPS", 0.99),
        ("isro", "gaganyaan_program", "DEVELOPS", 0.99),
        ("india", "aditya_l1_mission", "DEVELOPS", 0.99),
        ("isro", "navic", "OPERATES", 0.99),
        ("spacex", "starlink_constellation", "OPERATES", 0.99),
        ("china", "tiangong_space_station", "OPERATES", 0.99),
        ("china", "beidou_navigation", "OPERATES", 0.99),
        ("csa", "tiangong_space_station", "OPERATES", 0.99),
        ("nasa", "international_space_station", "OPERATES", 0.99),

        # === Telecom & digital ===
        ("huawei", "5g_networks", "DEVELOPS", 0.99),
        ("reliance_jio", "india_5g_rollout", "DEVELOPS", 0.99),
        ("bharti_airtel", "india_5g_rollout", "DEVELOPS", 0.99),
        ("india", "india_digital_public_infrastructure", "DEVELOPS", 0.99),
        ("india", "india_upi", "DEVELOPS", 0.99),
        ("india", "semiconductor_fabs_india", "DEVELOPS", 0.95),

        # === Tech competition ===
        ("semiconductors", "artificial_intelligence", "CRITICAL_FOR", 0.99),
        ("semiconductors", "5g_networks", "CRITICAL_FOR", 0.98),
        ("semiconductors", "armed_uav_drones", "CRITICAL_FOR", 0.95),
        ("rare_earth_elements", "ev_batteries", "CRITICAL_FOR", 0.97),
        ("lithium", "ev_batteries", "CRITICAL_FOR", 0.99),
        ("cobalt", "ev_batteries", "CRITICAL_FOR", 0.97),
        ("silicon", "semiconductors", "CRITICAL_FOR", 0.99),
        ("silicon", "solar_panels", "CRITICAL_FOR", 0.97),
        ("copper", "5g_networks", "CRITICAL_FOR", 0.93),
        ("copper", "ev_batteries", "CRITICAL_FOR", 0.92),
        ("graphite", "ev_batteries", "CRITICAL_FOR", 0.95),

        # === Companies → tech ===
        ("apple", "india", "OPERATES_IN", 0.97),
        ("foxconn", "india", "OPERATES_IN", 0.97),
        ("samsung_electronics", "india", "OPERATES_IN", 0.97),
        ("amazon_web_services", "india", "OPERATES_IN", 0.98),
        ("microsoft", "india", "OPERATES_IN", 0.98),
        ("google", "india", "OPERATES_IN", 0.98),
    ]


def generate_climate_edges():
    """Cross-domain climate edges."""
    return [
        # === Energy production ===
        ("india", "solar_energy", "PRODUCES", 0.98),
        ("india", "wind_energy", "PRODUCES", 0.97),
        ("india", "hydropower", "PRODUCES", 0.98),
        ("india", "nuclear_energy", "PRODUCES", 0.97),
        ("india", "coal", "PRODUCES", 0.99),
        ("china", "solar_energy", "PRODUCES", 0.99),
        ("china", "wind_energy", "PRODUCES", 0.99),
        ("usa", "solar_energy", "PRODUCES", 0.98),
        ("usa", "wind_energy", "PRODUCES", 0.98),
        ("brazil", "biofuels", "PRODUCES", 0.99),
        ("india", "biofuels", "PRODUCES", 0.93),

        # === Climate policies ===
        ("india", "paris_climate_agreement", "SIGNS", 0.99),
        ("china", "paris_climate_agreement", "SIGNS", 0.99),
        ("usa", "paris_climate_agreement", "SIGNS", 0.97),
        ("european_union", "eu_green_deal", "SIGNS", 0.99),
        ("european_union", "eu_cbam", "SIGNS", 0.99),
        ("india", "india_national_hydrogen_mission", "SIGNS", 0.99),
        ("india", "india_renewable_target", "SIGNS", 0.99),
        ("india", "india_net_zero_2070", "SIGNS", 0.99),
        ("usa", "us_ira", "SIGNS", 0.99),
        ("india", "international_solar_alliance", "LEADS", 0.99),

        # === Climate impacts ===
        ("global_warming", "sea_level_rise", "CAUSES", 0.99),
        ("global_warming", "extreme_weather_events", "CAUSES", 0.98),
        ("global_warming", "arctic_ice_melt", "CAUSES", 0.99),
        ("global_warming", "glacial_retreat_himalayas", "CAUSES", 0.98),
        ("global_warming", "coral_reef_bleaching", "CAUSES", 0.97),
        ("global_warming", "permafrost_thaw", "CAUSES", 0.97),
        ("sea_level_rise", "maldives", "THREATENS", 0.97),
        ("sea_level_rise", "bangladesh", "THREATENS", 0.96),
        ("sea_level_rise", "fiji", "THREATENS", 0.95),
        ("glacial_retreat_himalayas", "india", "THREATENS", 0.95),
        ("glacial_retreat_himalayas", "nepal", "THREATENS", 0.95),
        ("india_monsoon_disruption", "india", "AFFECTS", 0.96),
        ("india_monsoon_disruption", "wheat", "AFFECTS", 0.93),
        ("india_monsoon_disruption", "rice", "AFFECTS", 0.93),
        ("el_nino", "india_monsoon_disruption", "CAUSES", 0.90),
        ("delhi_air_pollution", "india", "AFFECTS", 0.95),
        ("india_heatwaves", "india", "AFFECTS", 0.96),
        ("water_scarcity_crisis", "india", "AFFECTS", 0.94),
        ("extreme_weather_events", "global_food_price_index", "INCREASES", 0.90),
        ("arctic_ice_melt", "arctic_northern_sea_route", "AFFECTS", 0.95),

        # === Clean energy infrastructure ===
        ("india", "india_solar_parks", "DEVELOPS", 0.99),
        ("india", "india_offshore_wind", "DEVELOPS", 0.95),
        ("india", "india_nuclear_fleet", "OPERATES", 0.99),
        ("india", "india_ethanol_blending", "DEVELOPS", 0.98),
        ("india", "india_ev_charging_network", "DEVELOPS", 0.93),
        ("india", "india_strategic_petroleum_reserve", "OPERATES", 0.98),

        # === Resource → climate links ===
        ("coal", "global_warming", "CAUSES", 0.98),
        ("crude_oil", "global_warming", "CAUSES", 0.97),
        ("natural_gas", "global_warming", "CAUSES", 0.90),
        ("hydrogen", "global_warming", "MITIGATES", 0.88),
        ("solar_energy", "global_warming", "MITIGATES", 0.95),
        ("wind_energy", "global_warming", "MITIGATES", 0.95),
        ("nuclear_energy", "global_warming", "MITIGATES", 0.92),

        # === EU policy impacts ===
        ("eu_cbam", "india", "AFFECTS", 0.93),
        ("eu_cbam", "steel", "AFFECTS", 0.95),
        ("eu_cbam", "aluminum", "AFFECTS", 0.94),
        ("eu_green_deal", "india", "AFFECTS", 0.88),
    ]


def generate_society_edges():
    """Cross-domain society edges."""
    return [
        # === Demographics ===
        ("india_population", "india", "AFFECTS", 0.99),
        ("india_median_age", "india", "AFFECTS", 0.97),
        ("india_urbanization_rate", "india", "AFFECTS", 0.96),
        ("india_stem_graduates", "india", "AFFECTS", 0.93),
        ("india_startup_ecosystem", "india", "AFFECTS", 0.92),

        # === Diaspora & remittances ===
        ("indian_diaspora_gcc", "remittances", "SOURCE_OF", 0.99),
        ("indian_diaspora_usa", "india", "AFFECTS", 0.95),
        ("remittances", "india_current_account_deficit", "AFFECTS", 0.93),
        ("2026_iran_conflict", "indian_diaspora_gcc", "THREATENS", 0.90),

        # === Healthcare ===
        ("india", "india_healthcare_system", "OPERATES", 0.99),
        ("india", "ayushman_bharat", "SIGNS", 0.99),
        ("india", "india_vaccine_manufacturing", "DEVELOPS", 0.99),
        ("serum_institute_of_india", "india_vaccine_manufacturing", "DEVELOPS", 0.99),
        ("serum_institute_of_india", "india", "HEADQUARTERED_IN", 0.99),
        ("biocon", "india", "HEADQUARTERED_IN", 0.99),
        ("dr_reddys_laboratories", "india", "HEADQUARTERED_IN", 0.99),
        ("cipla", "india", "HEADQUARTERED_IN", 0.99),
        ("sun_pharma", "india", "HEADQUARTERED_IN", 0.99),
        ("india", "pharmaceuticals", "EXPORTS", 0.99),
        ("sun_pharma", "pharmaceuticals", "PRODUCES", 0.98),
        ("cipla", "pharmaceuticals", "PRODUCES", 0.97),
        ("dr_reddys_laboratories", "pharmaceuticals", "PRODUCES", 0.97),

        # === Education ===
        ("india", "india_new_education_policy", "SIGNS", 0.99),
        ("india_iit_system", "india", "AFFECTS", 0.95),
        ("india_iim_system", "india", "AFFECTS", 0.93),

        # === Food security ===
        ("india", "wheat", "PRODUCES", 0.99),
        ("india", "rice", "PRODUCES", 0.99),
        ("global_food_security", "india", "AFFECTS", 0.93),
        ("india_monsoon_disruption", "global_food_security", "AFFECTS", 0.90),
        ("russia_ukraine_war", "global_food_security", "AFFECTS", 0.95),

        # === Soft power ===
        ("india", "india_g20_presidency_2023", "PARTICIPATES_IN", 0.99),
        ("india", "india_un_security_council_bid", "PARTICIPATES_IN", 0.97),
        ("india_soft_power", "india", "AFFECTS", 0.90),
    ]


# ═══════════════════════════════════════════════════════════════════
# SUPPLEMENTARY: Additional 400+ nodes and edges to reach 1000+
# ═══════════════════════════════════════════════════════════════════

def generate_supplementary_nodes():
    """Additional nodes across all domains to reach 1000+ total."""
    nodes = [
        # === INDIAN STATES & CITIES (key economic hubs) ===
        ("maharashtra", "Location", "India's most industrialized state, home to Mumbai financial capital"),
        ("gujarat", "Location", "India's western state, major port infrastructure and refining hub"),
        ("tamil_nadu", "Location", "South Indian state with auto manufacturing and IT sector in Chennai"),
        ("karnataka", "Location", "South Indian state housing Bangalore IT capital of India"),
        ("telangana", "Location", "South Indian state with Hyderabad tech and pharma hub"),
        ("delhi_ncr", "Location", "India's capital region and major political-economic center"),
        ("west_bengal", "Location", "Eastern Indian state with Kolkata port and industrial base"),
        ("uttar_pradesh", "Location", "India's most populous state with emerging defense corridor"),
        ("rajasthan", "Location", "Western Indian state with solar energy and mineral resources"),
        ("kerala", "Location", "Southern Indian state with high remittance dependence on Gulf workers"),
        ("andhra_pradesh", "Location", "Southeast Indian state with Visakhapatnam port and IT corridor"),
        ("madhya_pradesh", "Location", "Central Indian state with agricultural production base"),
        ("punjab", "Location", "Northern Indian state and breadbasket for wheat production"),
        ("haryana", "Location", "Northern Indian state with Gurugram corporate hub near Delhi"),
        ("odisha", "Location", "Eastern Indian state with mineral resources and Paradip port"),
        ("jharkhand", "Location", "Eastern Indian state with coal and mineral reserves"),
        ("assam", "Location", "Northeastern Indian state with oil production and tea estates"),
        ("goa", "Location", "Western Indian state with iron ore mining and tourism"),
        ("mumbai", "Location", "India's financial capital hosting BSE and NSE stock exchanges"),
        ("bangalore", "Location", "India's Silicon Valley and IT capital in Karnataka"),
        ("chennai", "Location", "South Indian city with major auto and electronics manufacturing"),
        ("hyderabad", "Location", "South Indian city known as Genome Valley and IT hub"),
        ("pune", "Location", "Western Indian city with automotive and defense manufacturing"),
        ("kolkata", "Location", "Eastern Indian city with port and heavy industry base"),
        ("ahmedabad", "Location", "Gujarat city with textile and pharmaceutical industries"),
        ("jamnagar", "Location", "Gujarat city hosting world's largest oil refinery by Reliance"),
        ("visakhapatnam", "Location", "Eastern Indian city with naval base and strategic petroleum reserve"),
        ("kochi", "Location", "Kerala city with international container transshipment terminal"),
        ("lucknow", "Location", "Capital of Uttar Pradesh on UP defense corridor"),
        ("varanasi", "Location", "Historic Indian city and constituency of PM Modi"),

        # === MORE COMPANIES (Indian + global) ===
        ("paytm", "Company", "Indian fintech company and digital payments platform"),
        ("zomato", "Company", "Indian food delivery and restaurant platform"),
        ("ola_electric", "Company", "Indian electric vehicle manufacturer for two-wheelers"),
        ("delhivery", "Company", "Indian logistics and supply chain company"),
        ("razorpay", "Company", "Indian fintech infrastructure company for payments"),
        ("flipkart", "Company", "Indian e-commerce major owned by Walmart"),
        ("byju", "Company", "Indian edtech company with global education platform"),
        ("ola_cabs", "Company", "Indian ride-hailing and mobility platform"),
        ("bharti_enterprises", "Company", "Indian conglomerate in telecom, agri-business, and financial services"),
        ("godrej_group", "Company", "Indian diversified conglomerate in FMCG, real estate, and agriculture"),
        ("hero_motocorp", "Company", "World's largest two-wheeler manufacturer by volume"),
        ("maruti_suzuki", "Company", "India's largest passenger car manufacturer"),
        ("ashok_leyland", "Company", "India's second largest commercial vehicle manufacturer"),
        ("bharat_forge", "Company", "India's largest forging company serving auto and defense sectors"),
        ("sun_pharmaceutical", "Company", "India's largest pharma company by market cap"),
        ("lupin", "Company", "Indian pharma company specializing in generics for global markets"),
        ("aurobindo_pharma", "Company", "Indian pharmaceutical company with global API operations"),
        ("torrent_pharma", "Company", "Indian pharmaceutical company with domestic and international presence"),
        ("havells_india", "Company", "Indian electrical equipment and consumer goods manufacturer"),
        ("titan_company", "Company", "India's leading watch and jewelry manufacturer, Tata Group"),
        ("dabur", "Company", "Indian FMCG company specializing in Ayurvedic products"),
        ("itc_limited", "Company", "Indian diversified conglomerate in FMCG, hotels, agriculture"),
        ("hindustan_unilever", "Company", "India's largest FMCG company, Unilever subsidiary"),
        ("nestle_india", "Company", "Indian food processing subsidiary of Nestle global"),
        ("ultratech_cement", "Company", "India's largest cement manufacturer, Aditya Birla Group"),
        ("ambuja_cements", "Company", "Indian cement maker acquired by Adani Group"),
        ("acc_limited", "Company", "Indian cement manufacturer, part of Adani portfolio"),
        ("power_grid_corporation", "Company", "India's central transmission utility managing national grid"),
        ("solar_energy_corporation", "Company", "Indian government entity implementing national solar targets"),
        ("nhpc", "Company", "India's largest hydroelectric power company"),
        ("indian_railways", "Company", "India's state railway operator, world's fourth largest network"),
        ("konkan_railway", "Company", "Indian railway operating along western coast with strategic tunnels"),
        ("airports_authority_of_india", "Company", "Manager of 137 airports across India"),
        ("nhai", "Company", "National Highways Authority of India managing 140,000 km road network"),
        ("irctc", "Company", "Indian railway catering and tourism subsidiary"),
        ("garden_reach_shipbuilders", "Company", "Indian shipbuilding company constructing frigates and patrol vessels"),
        ("goa_shipyard", "Company", "Indian defense shipbuilder constructing naval vessels"),
        ("bharat_dynamics", "Company", "Indian defense company manufacturing missiles and weapons systems"),
        ("mishra_dhatu_nigam", "Company", "Indian special alloys manufacturer for defense and space"),
        ("data_patterns", "Company", "Indian defense electronics company for radar and communication"),
        ("kalyani_group", "Company", "Indian conglomerate in defense, automotive, and specialty chemicals"),
        ("zensar_technologies", "Company", "Indian IT services company, RPG Group"),
        ("tech_mahindra", "Company", "Indian IT services company, Mahindra Group"),
        ("mphasis", "Company", "Indian IT services company, Blackstone owned"),
        ("persistent_systems", "Company", "Indian software and technology services company"),
        ("coforge", "Company", "Indian IT services and digital transformation company"),
        ("lt_technology_services", "Company", "L&T subsidiary for engineering and technology services"),
        ("lt_mindtree", "Company", "L&T subsidiary for IT consulting and digital solutions"),
        ("tata_consultancy_services", "Company", "India's largest IT company and TCS brand parent entity"),
        ("tata_power", "Company", "Indian power generation and distribution company, Tata Group"),
        ("tata_chemicals", "Company", "Indian chemicals manufacturer and soda ash producer, Tata Group"),
        ("tata_communications", "Company", "Indian telecom infrastructure provider, submarine cable operator"),
        ("hdfc_life", "Company", "Indian life insurance company"),
        ("icici_bank", "Company", "India's second largest private sector bank"),
        ("axis_bank", "Company", "India's third largest private sector bank"),
        ("kotak_mahindra_bank", "Company", "Indian private sector bank and financial services"),
        ("bandhan_bank", "Company", "Indian microfinance-turned-universal bank"),
        ("bajaj_finance", "Company", "India's largest non-banking financial company"),
        ("nse_india", "Company", "National Stock Exchange of India, world's largest derivatives exchange"),
        ("bse_india", "Company", "Bombay Stock Exchange, Asia's oldest stock exchange"),
        ("schneider_electric", "Company", "French energy management company with India operations"),
        ("siemens", "Company", "German industrial conglomerate with India energy and rail operations"),
        ("honeywell", "Company", "US industrial technology company with India R&D centers"),
        ("general_electric", "Company", "US industrial conglomerate in aviation, power, and healthcare"),
        ("mitsubishi_heavy", "Company", "Japanese industrial conglomerate in defense and energy"),
        ("kawasaki_heavy", "Company", "Japanese manufacturer of submarines and railway systems"),
        ("hanwha_defense", "Company", "South Korean defense company manufacturing K9 howitzer"),
        ("rheinmetall", "Company", "German defense company manufacturing armored vehicles and munitions"),
        ("dassault_aviation", "Company", "French defense company manufacturing Rafale and Falcon jets"),
        ("saab", "Company", "Swedish defense company manufacturing Gripen fighter and submarines"),
        ("embraer", "Company", "Brazilian aerospace company manufacturing military and civilian aircraft"),
        ("turkish_aerospace", "Company", "Turkish defense company manufacturing Bayraktar drones"),
        ("korea_aerospace", "Company", "South Korean aerospace company manufacturing KF-21 fighter"),
        ("almaz_antey", "Company", "Russian defense company manufacturing S-400 and S-500 systems"),
        ("rostec", "Company", "Russian state defense conglomerate manufacturing military equipment"),
        ("norinco", "Company", "Chinese state defense company manufacturing weapons and vehicles"),
        ("avic", "Company", "Aviation Industry Corporation of China manufacturing J-20 fighter"),
        ("vale", "Company", "Brazilian mining giant, world's largest iron ore producer"),
        ("bhp", "Company", "Australian mining company, world's largest by market cap"),
        ("rio_tinto", "Company", "Anglo-Australian mining company in iron ore and aluminum"),
        ("glencore", "Company", "Swiss commodities trading and mining company"),
        ("anglo_american", "Company", "British mining company with diversified mineral portfolio"),
        ("freeport_mcmoran", "Company", "US mining company operating world's largest gold and copper mine"),
        ("albemarle", "Company", "US specialty chemicals company and largest lithium producer"),
        ("sqm", "Company", "Chilean lithium and fertilizer producer"),
        ("ganfeng_lithium", "Company", "Chinese lithium producer and battery recycler"),
        ("pilbara_minerals", "Company", "Australian lithium producer in Pilgangoora"),
        ("first_quantum_minerals", "Company", "Canadian miner operating in Zambia and Panama"),

        # === MORE ORGANIZATIONS ===
        ("world_economic_forum", "Organization", "International organization for public-private cooperation in Davos"),
        ("nuclear_suppliers_group", "Organization", "Group of 48 nations controlling nuclear material exports"),
        ("missile_technology_control_regime", "Organization", "Informal partnership limiting missile proliferation"),
        ("wassenaar_arrangement", "Organization", "Multilateral export control regime for conventional arms and dual-use goods"),
        ("financial_stability_board", "Organization", "International body monitoring global financial system"),
        ("bis", "Organization", "Bank for International Settlements coordinating central bank policy"),
        ("oecd", "Organization", "Organisation for Economic Co-operation and Development"),
        ("apec", "Organization", "Asia-Pacific Economic Cooperation forum"),
        ("bimstec", "Organization", "Bay of Bengal Initiative for Multi-Sectoral Technical and Economic Cooperation"),
        ("saarc", "Organization", "South Asian Association for Regional Cooperation"),
        ("csto", "Organization", "Collective Security Treaty Organization led by Russia"),
        ("mercosur", "Organization", "South American trade bloc including Brazil and Argentina"),
        ("ecowas", "Organization", "Economic Community of West African States"),
        ("sadc", "Organization", "Southern African Development Community"),
        ("pacific_islands_forum", "Organization", "Regional organization of Pacific island states"),
        ("osce", "Organization", "Organization for Security and Cooperation in Europe"),
        ("unsc", "Organization", "United Nations Security Council with 5 permanent members"),
        ("unga", "Organization", "United Nations General Assembly of all 193 member states"),
        ("opcw", "Organization", "Organisation for the Prohibition of Chemical Weapons"),
        ("ctbto", "Organization", "Comprehensive Nuclear-Test-Ban Treaty Organization"),
        ("iter", "Organization", "International fusion energy project in France"),
        ("cern", "Organization", "European Organization for Nuclear Research"),
        ("icrc", "Organization", "International Committee of the Red Cross humanitarian aid"),
        ("unicef", "Organization", "United Nations Children's Fund for child welfare"),
        ("unhcr", "Organization", "United Nations High Commissioner for Refugees"),
        ("fao", "Organization", "Food and Agriculture Organization of the United Nations"),
        ("wmo", "Organization", "World Meteorological Organization monitoring climate"),
        ("ipcc", "Organization", "Intergovernmental Panel on Climate Change"),
        ("unep", "Organization", "United Nations Environment Programme"),
        ("irena", "Organization", "International Renewable Energy Agency"),
        ("iea", "Organization", "International Energy Agency monitoring global energy markets"),
        ("unctad", "Organization", "United Nations Conference on Trade and Development"),
        ("drdo", "Organization", "India's Defence Research and Development Organisation"),
        ("dac", "Organization", "India's Defence Acquisition Council overseeing procurement"),
        ("niti_aayog", "Organization", "India's policy think tank replacing Planning Commission"),
        ("sebi", "Organization", "Securities and Exchange Board of India regulating capital markets"),
        ("irdai", "Organization", "Insurance Regulatory and Development Authority of India"),
        ("trai", "Organization", "Telecom Regulatory Authority of India"),
        ("dgca", "Organization", "Directorate General of Civil Aviation India"),
        ("indian_coast_guard", "Organization", "Maritime law enforcement and search-and-rescue"),
        ("bsf", "Organization", "Border Security Force of India guarding international borders"),
        ("cisf", "Organization", "Central Industrial Security Force protecting critical infrastructure"),
        ("raw", "Organization", "Research and Analysis Wing, India's external intelligence agency"),
        ("ib", "Organization", "Intelligence Bureau, India's internal intelligence agency"),
        ("nscs", "Organization", "National Security Council Secretariat of India"),
        ("ntro", "Organization", "National Technical Research Organisation for technical intelligence"),
        ("cert_in", "Organization", "Indian Computer Emergency Response Team for cybersecurity"),
        ("npci", "Organization", "National Payments Corporation of India operating UPI"),
        ("nabard", "Organization", "National Bank for Agriculture and Rural Development"),
        ("exim_bank", "Organization", "Export-Import Bank of India financing international trade"),
        ("sidbi", "Organization", "Small Industries Development Bank of India"),

        # === MORE AGREEMENTS & TREATIES ===
        ("chabahar_agreement", "Agreement", "India-Iran agreement for development of Chabahar port"),
        ("india_japan_nuclear_deal", "Agreement", "2017 civil nuclear cooperation agreement"),
        ("india_us_beca", "Agreement", "Basic Exchange and Cooperation Agreement for geospatial intelligence"),
        ("india_us_lemoa", "Agreement", "Logistics Exchange Memorandum of Agreement for military logistics"),
        ("india_us_comcasa", "Agreement", "Communications Compatibility and Security Agreement"),
        ("india_france_strategic_partnership", "Agreement", "India-France defense and strategic cooperation pact"),
        ("india_russia_s400_deal", "Agreement", "India's $5.4B deal for S-400 missile defense systems"),
        ("abraham_accords", "Agreement", "2020 normalization agreements between Israel and Arab states"),
        ("aukus_submarine_deal", "Agreement", "Agreement for Australia to acquire nuclear-powered submarines"),
        ("minsk_agreements", "Agreement", "Ceasefire agreements for Russia-Ukraine conflict in Donbas"),
        ("camp_david_accords", "Agreement", "1978 Egypt-Israel peace treaty framework"),
        ("india_mauritius_cecpa", "Agreement", "India-Mauritius Comprehensive Economic Cooperation and Partnership"),
        ("india_japan_industrial_corridors", "Agreement", "India-Japan cooperation for industrial corridor development"),
        ("quad_vaccine_initiative", "Agreement", "Quad agreement to deliver vaccines to Indo-Pacific"),
        ("india_middle_east_food_corridor", "Agreement", "Emerging food security corridor linking India to Middle East"),
        ("antarctic_treaty", "Agreement", "International agreement governing Antarctica for peaceful purposes"),
        ("outer_space_treaty", "Agreement", "Treaty governing activities of states in outer space"),
        ("unclos", "Agreement", "United Nations Convention on the Law of the Sea"),
        ("npt", "Agreement", "Nuclear Non-Proliferation Treaty restricting nuclear weapons spread"),
        ("ctbt", "Agreement", "Comprehensive Nuclear-Test-Ban Treaty"),

        # === MORE PERSONS ===
        ("rajnath_singh", "Person", "India's Defence Minister overseeing military modernization"),
        ("nirmala_sitharaman", "Person", "India's Finance Minister managing fiscal policy and budgets"),
        ("g_satheesh_reddy", "Person", "Former DRDO Chairman who led mission-mode defense programs"),
        ("s_somanath", "Person", "ISRO Chairman leading Chandrayaan-3 and Gaganyaan programs"),
        ("mukesh_ambani", "Person", "Chairman of Reliance Industries, India's richest person"),
        ("gautam_adani", "Person", "Chairman of Adani Group, major ports and energy tycoon"),
        ("ratan_tata", "Person", "Chairman Emeritus of Tata Sons, iconic Indian industrialist"),
        ("sunder_pichai", "Person", "CEO of Google and Alphabet, Indian-American tech leader"),
        ("satya_nadella", "Person", "CEO of Microsoft, Indian-American tech leader"),
        ("abdel_fattah_el_sisi", "Person", "President of Egypt and Suez Canal corridor leader"),
        ("lula_da_silva", "Person", "President of Brazil and BRICS advocate"),
        ("joe_biden", "Person", "Former US President who expanded AUKUS and CHIPS Act"),
        ("macron", "Person", "President of France and Indo-Pacific strategy advocate"),
        ("olaf_scholz", "Person", "Chancellor of Germany and Zeitenwende defense policy leader"),
        ("kishida_fumio", "Person", "Former Japan PM who doubled defense budget commitment"),
        ("ismail_haniyeh", "Person", "Former Hamas political bureau chief"),
        ("hassan_nasrallah", "Person", "Former Hezbollah Secretary-General"),
        ("kim_jong_un", "Person", "Supreme Leader of North Korea with nuclear weapons program"),
        ("shavkat_mirziyoyev", "Person", "President of Uzbekistan reforming Central Asian connectivity"),
        ("sheikh_hasina", "Person", "Former PM of Bangladesh who led economic growth era"),
        ("anwar_ibrahim", "Person", "Prime Minister of Malaysia managing South China Sea balance"),
        ("prabowo_subianto", "Person", "President of Indonesia and largest ASEAN economy leader"),
        ("cyril_ramaphosa", "Person", "President of South Africa and BRICS host"),
        ("william_lai", "Person", "President of Taiwan managing cross-strait relations"),
        ("pope_francis", "Person", "Head of Catholic Church with global diplomatic influence"),
        ("elon_musk", "Person", "CEO of Tesla and SpaceX, influential in tech and space"),
        ("jensen_huang", "Person", "CEO of Nvidia leading AI chip revolution"),
        ("sam_altman", "Person", "CEO of OpenAI driving generative AI development"),
        ("tim_cook", "Person", "CEO of Apple diversifying manufacturing to India"),

        # === MORE INFRASTRUCTURE ===
        ("delhi_mumbai_industrial_corridor", "Infrastructure", "India's $100B industrial mega-corridor across 6 states"),
        ("chennai_bangalore_industrial_corridor", "Infrastructure", "South India industrial corridor connecting two tech hubs"),
        ("amritsar_kolkata_industrial_corridor", "Infrastructure", "North-South freight corridor on Grand Trunk Road route"),
        ("up_defense_corridor", "Infrastructure", "Uttar Pradesh defense manufacturing corridor with ₹20,000 crore investment"),
        ("tamil_nadu_defense_corridor", "Infrastructure", "Tamil Nadu defense manufacturing corridor"),
        ("india_japan_bullet_train", "Infrastructure", "Mumbai-Ahmedabad high-speed rail project with Japanese technology"),
        ("metro_rail_network_india", "Infrastructure", "India's expanding metro rail across 20+ cities"),
        ("national_gas_grid", "Infrastructure", "India's 35,000 km gas pipeline network expansion"),
        ("india_refinery_complex_jamnagar", "Infrastructure", "World's largest oil refinery complex by Reliance in Gujarat"),
        ("india_refinery_paradip", "Infrastructure", "IOCL's 300,000 bpd refinery on east coast"),
        ("india_refinery_vadinar", "Infrastructure", "Nayara Energy's 400,000 bpd refinery in Gujarat"),
        ("cpec", "Infrastructure", "China-Pakistan Economic Corridor with $62B investment"),
        ("china_laos_railway", "Infrastructure", "Railway connecting Kunming to Vientiane operational since 2021"),
        ("jakarta_bandung_hsr", "Infrastructure", "Indonesia's first high-speed rail built with Chinese technology"),
        ("trans_siberian_railway", "Infrastructure", "Russia's 9,289 km railway connecting Moscow to Vladivostok"),
        ("suez_canal_expansion", "Infrastructure", "2015 expansion doubling capacity of Suez Canal"),
        ("three_seas_initiative", "Infrastructure", "EU initiative connecting Adriatic, Baltic, and Black Sea infrastructure"),
        ("lobito_corridor", "Infrastructure", "US-backed rail corridor from DRC and Zambia to Angola's Atlantic port"),
        ("mombasa_nairobi_sgr", "Infrastructure", "Chinese-built standard gauge railway in Kenya"),
        ("lamu_port", "Infrastructure", "Kenya's new deep-water port on LAPSSET corridor"),
        ("gwadar_kashgar_highway", "Infrastructure", "Road link connecting Gwadar port to western China"),
        ("karakoram_highway", "Infrastructure", "Pakistan-China highway through Khunjerab Pass"),
        ("international_solar_alliance_hq", "Infrastructure", "ISA headquarters in Gurugram, India"),
        ("india_green_hydrogen_hubs", "Infrastructure", "Planned green hydrogen production zones in Gujarat and Rajasthan"),
        ("kudankulam_nuclear_plant", "Infrastructure", "India-Russia nuclear power plant in Tamil Nadu"),
        ("jaitapur_nuclear_plant", "Infrastructure", "Planned India-France nuclear power plant in Maharashtra, world's largest"),
        ("rooppur_nuclear_plant", "Infrastructure", "Russia-built nuclear plant in Bangladesh"),

        # === MORE EVENTS ===
        ("india_china_galwan_clash", "Event", "2020 deadly border clash between Indian and Chinese forces in Ladakh"),
        ("pulwama_attack", "Event", "2019 terrorist attack on Indian paramilitary in Kashmir"),
        ("balakot_air_strike", "Event", "2019 Indian air strike on terrorist camp in Pakistan"),
        ("doklam_standoff", "Event", "2017 India-China military standoff at Bhutan-China-India trijunction"),
        ("abrogation_article_370", "Event", "2019 India's revocation of special status of Jammu and Kashmir"),
        ("afghanistan_taliban_takeover", "Event", "August 2021 Taliban seizure of power in Afghanistan"),
        ("ethiopia_tigray_conflict", "Event", "2020-2022 civil conflict in Ethiopia affecting regional stability"),
        ("libyan_civil_war", "Event", "Ongoing instability in Libya affecting Mediterranean migration and oil"),
        ("sahel_instability", "Event", "Growing security crisis in Mali, Niger, Burkina Faso with military coups"),
        ("global_ai_safety_summit", "Event", "International summits on AI governance and safety since 2023"),
        ("silicon_valley_bank_collapse", "Event", "2023 US banking crisis affecting global financial confidence"),
        ("evergrande_crisis", "Event", "Chinese property developer default destabilizing global markets"),
        ("fukushima_water_release", "Event", "2023 Japan's treated radioactive water release affecting fisheries"),
        ("india_lunar_south_pole_landing", "Event", "Chandrayaan-3 becoming first to land on Moon's south pole Aug 2023"),
        ("isro_aditya_l1_success", "Event", "India's first solar observatory reaching L1 point Jan 2024"),
        ("india_semiconductor_mission", "Event", "India's push for domestic chip manufacturing with $10B incentives"),
        ("digital_india_program", "Event", "India's flagship program for digital infrastructure and governance"),
        ("swachh_bharat_mission", "Event", "India's national cleanliness and sanitation campaign"),
        ("ayodhya_ram_temple", "Event", "Inauguration of Ram Temple in Ayodhya January 2024"),

        # === MORE ECONOMIC INDICATORS ===
        ("india_gst_collection", "Indicator", "India's monthly Goods and Services Tax revenue exceeding ₹1.8 lakh crore"),
        ("india_pmi", "Indicator", "India's Purchasing Managers Index indicating manufacturing and services growth"),
        ("india_trade_deficit", "Indicator", "India's merchandise trade deficit driven by oil and gold imports"),
        ("sensex", "Indicator", "BSE Sensex index of 30 leading Indian companies"),
        ("nifty_50", "Indicator", "NSE Nifty 50 blue-chip index tracking India's top companies"),
        ("india_infrastructure_spending", "Indicator", "India's annual capital expenditure on infrastructure exceeding $100B"),
        ("india_defense_budget", "Indicator", "India's defense allocation approximately $75B in 2025-26"),
        ("china_defense_budget", "Indicator", "China's defense budget approximately $230B, second largest globally"),
        ("us_defense_budget", "Indicator", "US defense budget approximately $886B, largest globally"),
        ("global_arms_trade_value", "Indicator", "International arms market worth $100B+ annually"),
        ("india_renewable_capacity", "Indicator", "India's installed renewable energy capacity exceeding 200 GW"),
        ("global_ev_sales", "Indicator", "Worldwide electric vehicle sales exceeding 14 million in 2023"),
        ("india_digital_payments_volume", "Indicator", "India processing 10B+ digital transactions monthly via UPI"),
        ("global_semiconductor_market", "Indicator", "Global semiconductor industry worth $580B in 2024"),
        ("india_remittance_inflows", "Indicator", "India receiving $120B+ annual remittances, world's largest recipient"),
        ("global_lng_trade_volume", "Indicator", "International LNG trade reaching 400+ MTPA"),
        ("india_coal_import_volume", "Indicator", "India importing 250+ million tonnes of coal annually"),
        ("india_gold_imports", "Indicator", "India importing 700-800 tonnes of gold annually"),
        ("india_pharma_export_value", "Indicator", "India's pharmaceutical exports worth $27B+ annually"),
        ("india_it_export_revenue", "Indicator", "India's IT-BPM industry exporting $200B+ annually"),

        # === MORE TECHNOLOGIES ===
        ("thorium_reactor", "Technology", "India's advanced nuclear technology leveraging domestic thorium reserves"),
        ("terahertz_communication", "Technology", "Next-generation wireless technology beyond 5G"),
        ("neuromorphic_computing", "Technology", "Brain-inspired computing architecture for AI efficiency"),
        ("solid_state_batteries", "Technology", "Next-gen battery technology with higher energy density and safety"),
        ("perovskite_solar_cells", "Technology", "Next-generation low-cost solar cell technology"),
        ("direct_air_capture", "Technology", "Technology to remove CO2 directly from atmosphere"),
        ("vertical_farming", "Technology", "Indoor agriculture technology for food security"),
        ("ocean_thermal_energy", "Technology", "Renewable energy from ocean temperature differentials"),
        ("space_debris_removal", "Technology", "Technology to clean up orbital debris threatening satellites"),
        ("anti_drone_systems", "Technology", "Counter-unmanned aerial system technologies for defense"),
        ("directed_energy_weapons", "Technology", "Laser and microwave weapon systems for defense"),
        ("scramjet_technology", "Technology", "Air-breathing hypersonic engine technology for missiles"),
        ("stealth_technology", "Technology", "Radar-evading design and materials for aircraft and ships"),
        ("underwater_communication", "Technology", "Acoustic and quantum communication for submarine operations"),
        ("swarm_drone_technology", "Technology", "Coordinated autonomous drone formations for military operations"),

        # === FINAL BATCH: additional entities to reach 1000+ ===
        # More countries
        ("ivory_coast", "Country", "West African nation, world's largest cocoa producer"),
        ("senegal", "Country", "West African nation with emerging oil and gas sector"),
        ("cameroon", "Country", "Central African nation with oil exports and port at Douala"),
        ("uganda", "Country", "East African landlocked nation with oil reserves"),
        ("rwanda", "Country", "Central African technology and innovation hub"),
        ("botswana", "Country", "Southern African nation with diamond reserves and good governance"),
        ("mauritius", "Country", "Indian Ocean island nation, financial hub and India strategic partner"),
        ("seychelles", "Country", "Indian Ocean island nation with Indian naval listening post"),
        ("oman", "Country", "Gulf state integrating into trade corridors, hosting shadow fleet"),
        ("jordan", "Country", "Middle Eastern kingdom with US military presence"),
        ("costa_rica", "Country", "Central American nation with Intel fab and renewable energy"),
        ("panama", "Country", "Central American nation controlling the Panama Canal"),
        ("peru", "Country", "South American nation with copper and lithium deposits"),
        ("ecuador", "Country", "South American nation and former OPEC member"),
        ("bolivia", "Country", "South American landlocked nation with lithium reserves"),
        ("cuba", "Country", "Caribbean island nation under US embargo with Russian ties"),
        ("iceland", "Country", "Nordic island nation with geothermal energy and strategic Arctic position"),
        ("ireland", "Country", "European tech hub hosting US multinational headquarters"),
        ("portugal", "Country", "European nation on Atlantic with Sines deep-water port"),
        ("slovakia", "Country", "Central European EU member with automotive industry"),
        ("croatia", "Country", "Southeast European NATO member on Three Seas Initiative"),
        ("bulgaria", "Country", "Southeast European NATO member on Black Sea coast"),
        ("lithuania", "Country", "Baltic NATO member with Russian exclave Kaliningrad neighbor"),
        ("latvia", "Country", "Baltic NATO member with Russian minority population"),
        ("estonia", "Country", "Baltic NATO member and digital governance pioneer"),

        # More global stock exchanges and financial centers
        ("london_stock_exchange", "Organization", "World's sixth largest stock exchange by market cap"),
        ("hong_kong_stock_exchange", "Organization", "Major Asian financial market gateway to China"),
        ("shanghai_stock_exchange", "Organization", "China's largest stock exchange"),
        ("tokyo_stock_exchange", "Organization", "Japan's primary stock exchange, third largest globally"),

        # More strategic locations
        ("line_of_actual_control", "Location", "Disputed India-China border in Ladakh and Arunachal Pradesh"),
        ("line_of_control", "Location", "De facto India-Pakistan border in Kashmir"),
        ("siachen_glacier", "Location", "World's highest battlefield between India and Pakistan"),
        ("south_pars_gas_field", "Location", "World's largest natural gas field shared by Iran and Qatar"),
        ("kashagan_oil_field", "Location", "World's largest field discovery in decades, Kazakhstan"),
        ("permian_basin", "Location", "US largest oil-producing region in Texas and New Mexico"),
        ("rumaila_oil_field", "Location", "Iraq's largest oil field producing 1.5 million bpd"),
        ("ghawar_oil_field", "Location", "World's largest conventional oil field in Saudi Arabia"),
        ("bombay_high", "Location", "India's largest offshore oil field operated by ONGC"),
        ("krishna_godavari_basin", "Location", "India's east coast gas basin operated by Reliance"),
        ("spratlys_islands", "Location", "Disputed island chain in South China Sea claimed by 6 nations"),
        ("paracel_islands", "Location", "Disputed South China Sea islands controlled by China"),
        ("senkaku_diaoyu_islands", "Location", "Disputed islands between Japan and China in East China Sea"),
        ("kuril_islands", "Location", "Disputed islands between Russia and Japan"),
        ("aksai_chin", "Location", "Region administered by China, claimed by India"),
        ("arunachal_pradesh", "Location", "Indian state claimed by China as 'South Tibet'"),
        ("ladakh", "Location", "Indian union territory bordering China and Pakistan, site of LAC tensions"),

        # More resources
        ("urea", "Resource", "Key nitrogen fertilizer, India is world's largest importer"),
        ("titanium", "Resource", "Aerospace and defense metal, India has significant beach sand deposits"),
        ("vanadium", "Resource", "Steel alloy and battery metal for grid-scale energy storage"),
        ("tungsten", "Resource", "Hard metal for industrial tools and military applications"),
        ("antimony", "Resource", "Critical mineral for military ordnance and flame retardants"),
        ("gallium", "Resource", "Critical mineral for semiconductors, China controls 80% of production"),
        ("germanium", "Resource", "Critical mineral for fiber optics and infrared systems, China-dominated"),

        # More international agreements/frameworks
        ("quad_chips_partnership", "Agreement", "Quad initiative for secure semiconductor supply chains"),
        ("minerals_security_partnership", "Agreement", "US-led coalition for critical mineral supply chain diversification"),
        ("blue_dot_network", "Agreement", "US-Japan-Australia initiative for quality infrastructure"),
        ("pgii", "Agreement", "Partnership for Global Infrastructure and Investment, G7 counter to BRI"),
        ("india_efta_tepa", "Agreement", "India-EFTA Trade and Economic Partnership Agreement 2024"),
        ("india_uk_fta_negotiations", "Agreement", "Ongoing India-UK free trade agreement discussions"),

        # More indicators
        ("india_defense_export_value", "Indicator", "India's growing defense exports reaching $2.5B target"),
        ("india_steel_production", "Indicator", "India producing 140+ MT of crude steel annually"),
        ("india_cement_production", "Indicator", "India producing 380+ MT of cement annually, second largest"),
        ("india_automobile_production", "Indicator", "India producing 25+ million vehicles annually"),
        ("india_startup_funding", "Indicator", "Indian startup ecosystem attracting $10B+ annually in VC funding"),
        ("global_rare_earth_demand", "Indicator", "Rising demand for rare earths driven by EVs and wind turbines"),

        # ── Push-to-1000 batch ──
        # More African / Latin American / Pacific countries
        ("ghana", "Country", "West African nation, cocoa and gold producer"),
        ("senegal", "Country", "West African nation, emerging oil and gas producer"),
        ("mozambique", "Country", "Southeast African nation, major LNG reserves"),
        ("tanzania", "Country", "East African nation, gas reserves and mineral wealth"),
        ("peru", "Country", "South American nation, copper and lithium reserves"),
        ("chile", "Country", "South American nation, world's largest copper producer"),
        ("colombia", "Country", "South American nation, oil and coal exporter"),
        ("fiji", "Country", "Pacific Island nation, climate vulnerability frontline"),
        ("papua_new_guinea", "Country", "Pacific nation, LNG exporter and mineral wealth"),
        ("mongolia", "Country", "Central Asian nation, vast mineral and coal reserves"),

        # More ports and maritime infrastructure
        ("chabahar_port", "Infrastructure", "India-developed strategic port in southeastern Iran"),
        ("gwadar_port", "Infrastructure", "China-developed deep-sea port in Balochistan, Pakistan"),
        ("hambantota_port", "Infrastructure", "Chinese-leased port in southern Sri Lanka"),
        ("duqm_port", "Infrastructure", "Oman's deep-water port, India has access agreement"),
        ("colombo_port", "Infrastructure", "Sri Lanka's main commercial port, largest in South Asia"),
        ("port_of_singapore", "Infrastructure", "World's busiest transshipment port"),
        ("port_of_shanghai", "Infrastructure", "World's busiest container port by volume"),
        ("port_of_rotterdam", "Infrastructure", "Europe's largest port, key energy gateway"),

        # Space and satellite programs
        ("isro", "Organization", "Indian Space Research Organisation"),
        ("nasa", "Organization", "US National Aeronautics and Space Administration"),
        ("esa", "Organization", "European Space Agency"),
        ("jaxa", "Organization", "Japan Aerospace Exploration Agency"),
        ("chandrayaan_3", "Event", "India's successful lunar landing mission 2023"),
        ("gaganyaan", "Technology", "India's human spaceflight programme"),
        ("navic", "Technology", "India's regional navigation satellite system"),

        # Financial / economic entities
        ("asian_infrastructure_investment_bank", "Organization", "AIIB, China-initiated multilateral development bank"),
        ("new_development_bank", "Organization", "BRICS bank for infrastructure and sustainable development"),
        ("india_sovereign_wealth_fund", "Organization", "National Investment and Infrastructure Fund of India"),
        ("upi", "Technology", "India's Unified Payments Interface, real-time payment system"),
        ("digital_rupee", "Technology", "Reserve Bank of India's CBDC pilot"),
        ("swift", "Organization", "Global interbank financial telecommunication network"),

        # Final-25 push
        ("ecuador", "Country", "South American nation, oil exporter and OPEC member until 2020"),
        ("bolivia", "Country", "South American landlocked nation, lithium reserves"),
        ("uruguay", "Country", "South American nation, renewable energy leader"),
        ("costa_rica", "Country", "Central American nation, 99% renewable electricity"),
        ("namibia", "Country", "Southern African nation, green hydrogen potential"),
        ("zambia", "Country", "Southern African copper-belt nation"),
        ("zimbabwe", "Country", "Southern African nation, lithium and platinum reserves"),
        ("laos", "Country", "Southeast Asian nation, hydropower exporter"),
        ("cambodia", "Country", "Southeast Asian nation, Mekong river basin"),
        ("nepal", "Country", "South Asian nation, hydropower potential and India neighbor"),
        ("bhutan", "Country", "South Asian kingdom, hydropower exports to India"),
        ("maldives", "Country", "Indian Ocean island nation, climate-vulnerable"),
        ("mauritius", "Country", "Indian Ocean island nation, India investment corridor"),
        ("seychelles", "Country", "Indian Ocean island, India naval presence agreement"),
        ("madagascar", "Country", "Indian Ocean island nation, nickel and graphite"),
        ("international_solar_alliance", "Organization", "India-initiated treaty-based alliance for solar energy"),
        ("coalition_for_disaster_resilient_infrastructure", "Organization", "India-initiated partnership for resilient infra"),
        ("india_semiconductor_mission", "Policy", "India's $10B semiconductor fabrication initiative"),
        ("production_linked_incentive", "Policy", "India's PLI scheme for domestic manufacturing"),
        ("national_hydrogen_mission", "Policy", "India's green hydrogen production strategy"),
        ("smart_cities_mission", "Policy", "India's urban development and digitization programme"),
        ("sagarmala", "Infrastructure", "India's port-led development and coastal shipping programme"),
        ("bharatmala", "Infrastructure", "India's highway development project network"),
        ("dedicated_freight_corridor", "Infrastructure", "India's 3300km east-west freight rail corridors"),
        ("india_middle_east_europe_corridor", "Infrastructure", "IMEC rail-shipping corridor announced at G20 2023"),

        # Last-15 to hit 1000+
        ("kyrgyzstan", "Country", "Central Asian nation, Manas transit center and gold mining"),
        ("tajikistan", "Country", "Central Asian nation, aluminium production and hydropower"),
        ("turkmenistan", "Country", "Central Asian nation, 4th largest natural gas reserves"),
        ("greenland", "Location", "Arctic territory, critical mineral deposits and strategic location"),
        ("arctic_council", "Organization", "Intergovernmental forum for Arctic governance"),
        ("international_north_south_transport_corridor", "Infrastructure", "India-Iran-Russia multimodal corridor"),
        ("kaladan_multimodal_transit", "Infrastructure", "India-Myanmar transport project via Sittwe port"),
        ("india_japan_act_east_forum", "Agreement", "India-Japan strategic cooperation in northeast India"),
        ("rupee_trade_mechanism", "Policy", "India's bilateral trade settlement in INR"),
        ("one_sun_one_world_one_grid", "Policy", "India-proposed global solar grid interconnection"),
        ("india_ai_mission", "Policy", "India's $1.2B AI compute and innovation initiative"),
        ("india_digital_public_infrastructure", "Technology", "India stack: Aadhaar, UPI, DigiLocker ecosystem"),
        ("agni_v_missile", "MilitaryAsset", "India's ICBM with 5000+ km range"),
        ("ins_vikrant", "MilitaryAsset", "India's first indigenous aircraft carrier"),
        ("brahmos_missile", "MilitaryAsset", "India-Russia joint supersonic cruise missile"),
        ("tejas_fighter", "MilitaryAsset", "India's indigenous light combat aircraft"),
        ("pinaka_rocket_system", "MilitaryAsset", "India's indigenous multi-barrel rocket launcher"),
        ("s400_missile_system", "MilitaryAsset", "Russian-origin air defense system acquired by India"),
        ("rafale_fighter", "MilitaryAsset", "French Dassault fighter jet operated by India"),
        ("global_biofuels_alliance", "Organization", "India-initiated G20 alliance for biofuel adoption"),
        ("int_big_cat_alliance", "Organization", "India-initiated global alliance for big cat conservation"),
        ("indo_pacific_oceans_initiative", "Organization", "India-proposed maritime cooperation framework"),
        ("vaccine_maitri", "Policy", "India's COVID vaccine diplomacy initiative"),
        ("ayushman_bharat", "Policy", "India's public health insurance scheme for 500M people"),
        ("pm_gati_shakti", "Infrastructure", "India's national master plan for multimodal connectivity"),
        ("india_stack", "Technology", "India's open digital infrastructure layers"),
    ]
    return nodes


def generate_supplementary_edges():
    """Additional edges for supplementary nodes."""
    return [
        # === Indian states → India ===
        ("maharashtra", "india", "AFFECTS", 0.99),
        ("gujarat", "india", "AFFECTS", 0.99),
        ("tamil_nadu", "india", "AFFECTS", 0.99),
        ("karnataka", "india", "AFFECTS", 0.99),
        ("telangana", "india", "AFFECTS", 0.99),
        ("delhi_ncr", "india", "AFFECTS", 0.99),
        ("kerala", "india", "AFFECTS", 0.99),
        ("uttar_pradesh", "india", "AFFECTS", 0.99),
        ("rajasthan", "india", "AFFECTS", 0.99),
        ("west_bengal", "india", "AFFECTS", 0.99),
        ("andhra_pradesh", "india", "AFFECTS", 0.99),
        ("odisha", "india", "AFFECTS", 0.98),
        ("punjab", "india", "AFFECTS", 0.98),
        ("assam", "india", "AFFECTS", 0.97),

        # === Cities → states ===
        ("mumbai", "maharashtra", "AFFECTS", 0.99),
        ("bangalore", "karnataka", "AFFECTS", 0.99),
        ("chennai", "tamil_nadu", "AFFECTS", 0.99),
        ("hyderabad", "telangana", "AFFECTS", 0.99),
        ("pune", "maharashtra", "AFFECTS", 0.98),
        ("kolkata", "west_bengal", "AFFECTS", 0.99),
        ("ahmedabad", "gujarat", "AFFECTS", 0.99),
        ("jamnagar", "gujarat", "AFFECTS", 0.97),
        ("kochi", "kerala", "AFFECTS", 0.98),

        # === Companies → Indian cities ===
        ("nse_india", "mumbai", "HEADQUARTERED_IN", 0.99),
        ("bse_india", "mumbai", "HEADQUARTERED_IN", 0.99),
        ("hdfc_bank", "mumbai", "HEADQUARTERED_IN", 0.99),
        ("icici_bank", "mumbai", "HEADQUARTERED_IN", 0.99),
        ("tata_consultancy_services", "mumbai", "HEADQUARTERED_IN", 0.99),
        ("reliance_industries", "mumbai", "HEADQUARTERED_IN", 0.99),
        ("infosys", "bangalore", "HEADQUARTERED_IN", 0.99),
        ("wipro", "bangalore", "HEADQUARTERED_IN", 0.99),
        ("isro", "bangalore", "HEADQUARTERED_IN", 0.99),
        ("drdo", "delhi_ncr", "HEADQUARTERED_IN", 0.99),
        ("sun_pharma", "mumbai", "HEADQUARTERED_IN", 0.99),
        ("lupin", "mumbai", "HEADQUARTERED_IN", 0.99),
        ("bajaj_auto", "pune", "HEADQUARTERED_IN", 0.99),
        ("bajaj_finance", "pune", "HEADQUARTERED_IN", 0.99),
        ("serum_institute_of_india", "pune", "HEADQUARTERED_IN", 0.99),
        ("maruti_suzuki", "delhi_ncr", "HEADQUARTERED_IN", 0.99),
        ("hero_motocorp", "delhi_ncr", "HEADQUARTERED_IN", 0.99),

        # === Indian corridors ===
        ("india", "delhi_mumbai_industrial_corridor", "DEVELOPS", 0.99),
        ("japan", "delhi_mumbai_industrial_corridor", "INVESTS_IN", 0.97),
        ("india", "up_defense_corridor", "DEVELOPS", 0.99),
        ("india", "tamil_nadu_defense_corridor", "DEVELOPS", 0.99),
        ("india", "india_japan_bullet_train", "DEVELOPS", 0.98),
        ("japan", "india_japan_bullet_train", "INVESTS_IN", 0.97),
        ("india", "india_green_hydrogen_hubs", "DEVELOPS", 0.95),

        # === Defense ecosystems ===
        ("drdo", "brahmos_missile", "DEVELOPS", 0.99),
        ("drdo", "agni_v_missile", "DEVELOPS", 0.99),
        ("drdo", "akash_missile", "DEVELOPS", 0.99),
        ("drdo", "pinaka_mlrs", "DEVELOPS", 0.99),
        ("drdo", "tejas_lca", "DEVELOPS", 0.98),
        ("drdo", "ballistic_missile_defense", "DEVELOPS", 0.97),
        ("drdo", "anti_satellite_weapon", "DEVELOPS", 0.97),
        ("bharat_dynamics", "brahmos_missile", "MANUFACTURES", 0.97),
        ("bharat_dynamics", "akash_missile", "MANUFACTURES", 0.98),
        ("bharat_forge", "india", "SUPPLIES", 0.95),
        ("kalyani_group", "india", "SUPPLIES", 0.93),
        ("data_patterns", "india", "SUPPLIES", 0.91),
        ("garden_reach_shipbuilders", "india", "SUPPLIES", 0.95),
        ("goa_shipyard", "india", "SUPPLIES", 0.94),

        # === Global defense companies → countries ===
        ("rheinmetall", "germany", "HEADQUARTERED_IN", 0.99),
        ("dassault_aviation", "france", "HEADQUARTERED_IN", 0.99),
        ("saab", "sweden", "HEADQUARTERED_IN", 0.99),
        ("embraer", "brazil", "HEADQUARTERED_IN", 0.99),
        ("turkish_aerospace", "turkey", "HEADQUARTERED_IN", 0.99),
        ("korea_aerospace", "south_korea", "HEADQUARTERED_IN", 0.99),
        ("almaz_antey", "russia", "HEADQUARTERED_IN", 0.99),
        ("rostec", "russia", "HEADQUARTERED_IN", 0.99),
        ("norinco", "china", "HEADQUARTERED_IN", 0.99),
        ("avic", "china", "HEADQUARTERED_IN", 0.99),
        ("hanwha_defense", "south_korea", "HEADQUARTERED_IN", 0.99),
        ("dassault_aviation", "rafale_fighter", "MANUFACTURES", 0.99),
        ("almaz_antey", "s400_missile_system", "MANUFACTURES", 0.99),
        ("hanwha_defense", "india", "SUPPLIES", 0.90),

        # === Mining companies → resources ===
        ("vale", "iron_ore", "PRODUCES", 0.99),
        ("bhp", "iron_ore", "PRODUCES", 0.99),
        ("rio_tinto", "iron_ore", "PRODUCES", 0.99),
        ("glencore", "cobalt", "PRODUCES", 0.96),
        ("anglo_american", "platinum_group_metals", "PRODUCES", 0.97),
        ("freeport_mcmoran", "copper", "PRODUCES", 0.99),
        ("albemarle", "lithium", "PRODUCES", 0.99),
        ("sqm", "lithium", "PRODUCES", 0.99),
        ("ganfeng_lithium", "lithium", "PRODUCES", 0.98),
        ("pilbara_minerals", "lithium", "PRODUCES", 0.97),
        ("vale", "brazil", "HEADQUARTERED_IN", 0.99),
        ("bhp", "australia", "HEADQUARTERED_IN", 0.99),
        ("rio_tinto", "australia", "HEADQUARTERED_IN", 0.99),
        ("glencore", "switzerland", "HEADQUARTERED_IN", 0.99),
        ("albemarle", "usa", "HEADQUARTERED_IN", 0.99),
        ("sqm", "chile", "HEADQUARTERED_IN", 0.99),
        ("ganfeng_lithium", "china", "HEADQUARTERED_IN", 0.99),

        # === Indian persons → orgs ===
        ("mukesh_ambani", "reliance_industries", "LEADS", 0.99),
        ("gautam_adani", "adani_group", "LEADS", 0.99),
        ("rajnath_singh", "india", "AFFECTS", 0.97),
        ("nirmala_sitharaman", "india", "AFFECTS", 0.97),
        ("s_somanath", "isro", "LEADS", 0.99),
        ("sunder_pichai", "google", "LEADS", 0.99),
        ("satya_nadella", "microsoft", "LEADS", 0.99),
        ("elon_musk", "spacex", "LEADS", 0.99),
        ("elon_musk", "tesla", "LEADS", 0.99),
        ("jensen_huang", "nvidia", "LEADS", 0.99),
        ("tim_cook", "apple", "LEADS", 0.99),
        ("abdel_fattah_el_sisi", "egypt", "LEADS", 0.99),
        ("lula_da_silva", "brazil", "LEADS", 0.99),
        ("prabowo_subianto", "indonesia", "LEADS", 0.99),
        ("anwar_ibrahim", "malaysia", "LEADS", 0.99),
        ("cyril_ramaphosa", "south_africa", "LEADS", 0.99),
        ("william_lai", "taiwan", "LEADS", 0.99),
        ("kim_jong_un", "north_korea", "LEADS", 0.99),

        # === Agreements ===
        ("india", "chabahar_agreement", "SIGNS", 0.99),
        ("iran", "chabahar_agreement", "SIGNS", 0.99),
        ("india", "india_us_beca", "SIGNS", 0.99),
        ("usa", "india_us_beca", "SIGNS", 0.99),
        ("india", "india_us_lemoa", "SIGNS", 0.99),
        ("usa", "india_us_lemoa", "SIGNS", 0.99),
        ("india", "india_us_comcasa", "SIGNS", 0.99),
        ("usa", "india_us_comcasa", "SIGNS", 0.99),
        ("india", "india_france_strategic_partnership", "SIGNS", 0.99),
        ("france", "india_france_strategic_partnership", "SIGNS", 0.99),
        ("india", "india_russia_s400_deal", "SIGNS", 0.99),
        ("russia", "india_russia_s400_deal", "SIGNS", 0.99),
        ("israel", "abraham_accords", "SIGNS", 0.99),
        ("uae", "abraham_accords", "SIGNS", 0.99),
        ("bahrain", "abraham_accords", "SIGNS", 0.99),
        ("india", "unclos", "SIGNS", 0.97),
        ("india", "npt", "AFFECTS", 0.90),
        ("india", "india_japan_nuclear_deal", "SIGNS", 0.99),
        ("japan", "india_japan_nuclear_deal", "SIGNS", 0.99),

        # === Nuclear infrastructure ===
        ("india", "kudankulam_nuclear_plant", "OPERATES", 0.99),
        ("russia", "kudankulam_nuclear_plant", "DEVELOPS", 0.98),
        ("india", "jaitapur_nuclear_plant", "DEVELOPS", 0.95),
        ("france", "jaitapur_nuclear_plant", "DEVELOPS", 0.95),
        ("russia", "rooppur_nuclear_plant", "DEVELOPS", 0.98),
        ("bangladesh", "rooppur_nuclear_plant", "OPERATES", 0.97),

        # === CPEC / BRI infrastructure ===
        ("china", "cpec", "DEVELOPS", 0.99),
        ("pakistan", "cpec", "PARTICIPATES_IN", 0.99),
        ("china", "china_laos_railway", "DEVELOPS", 0.99),
        ("china", "jakarta_bandung_hsr", "DEVELOPS", 0.97),
        ("china", "mombasa_nairobi_sgr", "DEVELOPS", 0.98),
        ("china", "gwadar_kashgar_highway", "DEVELOPS", 0.98),

        # === Indicators linked ===
        ("sensex", "mumbai", "AFFECTS", 0.95),
        ("nifty_50", "mumbai", "AFFECTS", 0.95),
        ("india_gst_collection", "india", "AFFECTS", 0.97),
        ("india_defense_budget", "india", "AFFECTS", 0.96),
        ("india_trade_deficit", "india", "AFFECTS", 0.96),
        ("india_remittance_inflows", "india", "AFFECTS", 0.95),
        ("india_it_export_revenue", "india", "AFFECTS", 0.96),
        ("india_pharma_export_value", "india", "AFFECTS", 0.94),
        ("india_renewable_capacity", "india", "AFFECTS", 0.93),
        ("india_digital_payments_volume", "india_upi", "AFFECTS", 0.95),
        ("global_semiconductor_market", "semiconductors", "AFFECTS", 0.98),
        ("global_ev_sales", "ev_batteries", "AFFECTS", 0.96),
        ("global_lng_trade_volume", "lng", "AFFECTS", 0.95),

        # === Technology edges ===
        ("india", "thorium_reactor", "DEVELOPS", 0.95),
        ("drdo", "scramjet_technology", "DEVELOPS", 0.93),
        ("drdo", "anti_drone_systems", "DEVELOPS", 0.92),
        ("drdo", "directed_energy_weapons", "DEVELOPS", 0.88),
        ("india", "swarm_drone_technology", "DEVELOPS", 0.85),
        ("usa", "directed_energy_weapons", "DEVELOPS", 0.96),
        ("china", "directed_energy_weapons", "DEVELOPS", 0.93),
        ("india", "stealth_technology", "DEVELOPS", 0.85),
        ("usa", "stealth_technology", "DEVELOPS", 0.99),
        ("china", "stealth_technology", "DEVELOPS", 0.95),

        # === Indian org structure ===
        ("rbi", "india", "AFFECTS", 0.99),
        ("sebi", "india", "AFFECTS", 0.97),
        ("niti_aayog", "india", "AFFECTS", 0.96),
        ("npci", "india_upi", "OPERATES", 0.99),
        ("raw", "india", "AFFECTS", 0.95),
        ("indian_coast_guard", "indian_ocean", "OPERATES_IN", 0.97),
        ("cert_in", "cybersecurity", "DEVELOPS", 0.93),
        ("exim_bank", "india", "AFFECTS", 0.90),

        # === International orgs → domains ===
        ("iea", "crude_oil", "AFFECTS", 0.93),
        ("iea", "natural_gas", "AFFECTS", 0.92),
        ("irena", "solar_energy", "AFFECTS", 0.93),
        ("irena", "wind_energy", "AFFECTS", 0.93),
        ("ipcc", "global_warming", "AFFECTS", 0.99),
        ("fao", "global_food_security", "AFFECTS", 0.97),
        ("who", "global_pandemic_preparedness", "AFFECTS", 0.97),
        ("unhcr", "global_refugee_crisis", "AFFECTS", 0.96),
        ("iaea", "nuclear_energy", "AFFECTS", 0.98),
        ("fatf", "india", "AFFECTS", 0.90),
        ("wto", "global_trade_volume", "AFFECTS", 0.95),
        ("imf", "india", "AFFECTS", 0.92),
        ("world_bank", "india", "AFFECTS", 0.90),

        # === Indian events ===
        ("india_china_galwan_clash", "india", "AFFECTS", 0.98),
        ("india_china_galwan_clash", "china", "AFFECTS", 0.97),
        ("pulwama_attack", "india", "AFFECTS", 0.97),
        ("balakot_air_strike", "pakistan", "AFFECTS", 0.96),
        ("india_lunar_south_pole_landing", "isro", "AFFECTS", 0.99),
        ("india_semiconductor_mission", "semiconductors", "AFFECTS", 0.93),
        ("digital_india_program", "india_digital_public_infrastructure", "DEVELOPS", 0.97),

        # === Final batch edges ===
        ("mauritius", "india", "PARTNERS_WITH", 0.95),
        ("india", "seychelles", "PARTNERS_WITH", 0.90),
        ("panama", "panama_canal", "CONTROLS", 0.99),
        ("egypt", "suez_canal", "CONTROLS", 0.99),
        ("turkey", "bosphorus_strait", "CONTROLS", 0.99),
        ("singapore", "strait_of_malacca", "CONTROLS", 0.95),
        ("malaysia", "strait_of_malacca", "CONTROLS", 0.95),

        # Territorial disputes
        ("india", "line_of_actual_control", "CONFLICT_WITH", 0.95),
        ("china", "line_of_actual_control", "CONFLICT_WITH", 0.95),
        ("india", "line_of_control", "CONFLICT_WITH", 0.95),
        ("pakistan", "line_of_control", "CONFLICT_WITH", 0.95),
        ("india", "siachen_glacier", "CONTROLS", 0.97),
        ("china", "spratlys_islands", "CONFLICT_WITH", 0.93),
        ("philippines", "spratlys_islands", "CONFLICT_WITH", 0.93),
        ("vietnam", "paracel_islands", "CONFLICT_WITH", 0.90),
        ("china", "paracel_islands", "CONTROLS", 0.97),
        ("japan", "senkaku_diaoyu_islands", "CONTROLS", 0.95),
        ("china", "senkaku_diaoyu_islands", "CONFLICT_WITH", 0.93),
        ("russia", "kuril_islands", "CONTROLS", 0.97),
        ("japan", "kuril_islands", "CONFLICT_WITH", 0.92),
        ("china", "aksai_chin", "CONTROLS", 0.95),
        ("india", "aksai_chin", "CONFLICT_WITH", 0.95),
        ("india", "arunachal_pradesh", "CONTROLS", 0.99),
        ("china", "arunachal_pradesh", "CONFLICT_WITH", 0.90),
        ("india", "ladakh", "CONTROLS", 0.99),

        # Oil/gas fields
        ("iran", "south_pars_gas_field", "OPERATES", 0.99),
        ("qatar", "south_pars_gas_field", "OPERATES", 0.99),
        ("saudi_arabia", "ghawar_oil_field", "OPERATES", 0.99),
        ("iraq", "rumaila_oil_field", "OPERATES", 0.99),
        ("usa", "permian_basin", "OPERATES", 0.99),
        ("ongc", "bombay_high", "OPERATES", 0.99),
        ("reliance_industries", "krishna_godavari_basin", "OPERATES", 0.97),

        # Critical minerals
        ("china", "gallium", "PRODUCES", 0.99),
        ("china", "germanium", "PRODUCES", 0.99),
        ("china", "antimony", "PRODUCES", 0.95),
        ("gallium", "semiconductors", "CRITICAL_FOR", 0.97),
        ("germanium", "semiconductors", "CRITICAL_FOR", 0.95),

        # Quad/multilateral
        ("quad", "quad_chips_partnership", "SIGNS", 0.97),
        ("usa", "minerals_security_partnership", "LEADS", 0.98),
        ("usa", "pgii", "LEADS", 0.97),
        ("india", "india_efta_tepa", "SIGNS", 0.97),
        ("india", "india_uk_fta_negotiations", "PARTICIPATES_IN", 0.93),
        ("uk", "india_uk_fta_negotiations", "PARTICIPATES_IN", 0.93),

        # Baltic states ===
        ("estonia", "nato", "MEMBER_OF", 0.99),
        ("latvia", "nato", "MEMBER_OF", 0.99),
        ("lithuania", "nato", "MEMBER_OF", 0.99),
        ("croatia", "nato", "MEMBER_OF", 0.99),
        ("bulgaria", "nato", "MEMBER_OF", 0.99),

        # India indicators
        ("india_defense_export_value", "india", "AFFECTS", 0.94),
        ("india_steel_production", "india", "AFFECTS", 0.93),
        ("india_automobile_production", "india", "AFFECTS", 0.93),
        ("india_startup_funding", "india", "AFFECTS", 0.91),

        # ── Push-to-1000 batch edges ──
        # Port operations
        ("india", "chabahar_port", "DEVELOPS", 0.97),
        ("china", "gwadar_port", "DEVELOPS", 0.97),
        ("china", "hambantota_port", "CONTROLS", 0.95),
        ("india", "duqm_port", "OPERATES", 0.93),
        ("india", "colombo_port", "TRADES_WITH", 0.90),

        # Space relations
        ("isro", "chandrayaan_3", "DEVELOPS", 0.99),
        ("isro", "gaganyaan", "DEVELOPS", 0.98),
        ("isro", "navic", "DEVELOPS", 0.99),
        ("india", "isro", "FUNDS", 0.99),
        ("isro", "nasa", "COOPERATES_WITH", 0.94),
        ("japan", "jaxa", "FUNDS", 0.99),

        # Financial entities
        ("china", "asian_infrastructure_investment_bank", "FUNDS", 0.98),
        ("india", "asian_infrastructure_investment_bank", "MEMBER_OF", 0.97),
        ("india", "new_development_bank", "MEMBER_OF", 0.99),
        ("india", "upi", "DEVELOPS", 0.99),
        ("rbi", "digital_rupee", "DEVELOPS", 0.97),

        # Resource-rich countries
        ("chile", "copper", "PRODUCES", 0.98),
        ("peru", "copper", "PRODUCES", 0.95),
        ("mozambique", "lng", "PRODUCES", 0.93),
        ("ghana", "gold", "PRODUCES", 0.96),
        ("mongolia", "coal", "PRODUCES", 0.95),
        ("colombia", "crude_oil", "PRODUCES", 0.93),

        # Push-to-1000 extra edges
        ("nepal", "india", "BORDERS", 0.99),
        ("bhutan", "india", "BORDERS", 0.99),
        ("bhutan", "india", "TRADES_WITH", 0.97),
        ("india", "maldives", "COOPERATES_WITH", 0.94),
        ("india", "mauritius", "COOPERATES_WITH", 0.94),
        ("india", "seychelles", "DEFENSE_PARTNERSHIP_WITH", 0.92),
        ("india", "international_solar_alliance", "LEADS", 0.99),
        ("india", "coalition_for_disaster_resilient_infrastructure", "LEADS", 0.98),
        ("india", "global_biofuels_alliance", "LEADS", 0.97),
        ("india", "india_semiconductor_mission", "FUNDS", 0.98),
        ("india", "production_linked_incentive", "REGULATES", 0.97),
        ("india", "national_hydrogen_mission", "FUNDS", 0.96),
        ("india", "sagarmala", "DEVELOPS", 0.97),
        ("india", "bharatmala", "DEVELOPS", 0.97),
        ("india", "dedicated_freight_corridor", "DEVELOPS", 0.97),
        ("india", "india_middle_east_europe_corridor", "DEVELOPS", 0.96),
        ("india", "international_north_south_transport_corridor", "DEVELOPS", 0.96),
        ("india", "agni_v_missile", "DEVELOPS", 0.99),
        ("india", "ins_vikrant", "DEVELOPS", 0.99),
        ("india", "brahmos_missile", "DEVELOPS", 0.98),
        ("russia", "brahmos_missile", "DEVELOPS", 0.98),
        ("india", "tejas_fighter", "DEVELOPS", 0.99),
        ("india", "pinaka_rocket_system", "DEVELOPS", 0.99),
        ("russia", "s400_missile_system", "MANUFACTURES", 0.99),
        ("india", "s400_missile_system", "OPERATES", 0.97),
        ("france", "rafale_fighter", "MANUFACTURES", 0.99),
        ("india", "rafale_fighter", "OPERATES", 0.98),
        ("india", "indo_pacific_oceans_initiative", "LEADS", 0.97),
        ("india", "vaccine_maitri", "LEADS", 0.98),
        ("india", "ayushman_bharat", "FUNDS", 0.98),
        ("india", "pm_gati_shakti", "DEVELOPS", 0.97),
        ("india", "india_ai_mission", "FUNDS", 0.97),
    ]


# ═══════════════════════════════════════════════════════════════════
# PHASE 3: LLM VERIFICATION
# ═══════════════════════════════════════════════════════════════════

def verify_edges_with_llm(edges_batch, batch_num, total_batches):
    """Use Groq LLM to verify a batch of edges for accuracy."""
    import requests

    if not GROQ_API_KEY:
        logger.warning("No GROQ_API_KEY — skipping LLM verification")
        return edges_batch, []

    # Format edges for the prompt
    edge_lines = []
    for i, (src, tgt, rel, conf) in enumerate(edges_batch):
        edge_lines.append(f"{i+1}. {src} -[{rel}]-> {tgt} (confidence: {conf})")

    prompt = f"""You are a fact-checking expert verifying a knowledge graph about global geopolitics, economics, defense, technology, climate, and society with focus on India.

Review these {len(edges_batch)} edges and identify any that are FACTUALLY INCORRECT. Only flag edges where the relationship is wrong or the entities don't actually have this relationship. Do NOT flag edges just for being low confidence.

Edges to verify:
{chr(10).join(edge_lines)}

Respond with a JSON object:
{{
  "verified_correct": [list of edge numbers that are correct],
  "flagged_incorrect": [
    {{"edge_num": N, "reason": "brief explanation of why this is wrong"}}
  ]
}}

Be strict but fair. Most edges should be correct. Only flag genuinely wrong relationships."""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 2000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Parse JSON from response (handle markdown wrapping)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            if content.startswith("json"):
                content = content[4:].strip()

        result = json.loads(content)
        flagged = result.get("flagged_incorrect", [])

        if flagged:
            flagged_nums = {f["edge_num"] for f in flagged}
            logger.warning(
                "Batch %d/%d: LLM flagged %d/%d edges as incorrect",
                batch_num, total_batches, len(flagged), len(edges_batch),
            )
            for f in flagged:
                idx = f["edge_num"] - 1
                if 0 <= idx < len(edges_batch):
                    edge = edges_batch[idx]
                    logger.warning(
                        "  FLAGGED: %s -[%s]-> %s | Reason: %s",
                        edge[0], edge[2], edge[1], f.get("reason", ""),
                    )
            verified = [e for i, e in enumerate(edges_batch) if (i + 1) not in flagged_nums]
            rejected = [edges_batch[f["edge_num"] - 1] for f in flagged if 0 <= f["edge_num"] - 1 < len(edges_batch)]
            return verified, rejected
        else:
            logger.info("Batch %d/%d: All %d edges verified correct", batch_num, total_batches, len(edges_batch))
            return edges_batch, []

    except Exception as e:
        logger.error("LLM verification failed for batch %d: %s", batch_num, e)
        return edges_batch, []  # On failure, keep all edges


def verify_all_edges(all_edges, batch_size=40):
    """Verify edges in batches using LLM."""
    verified = []
    rejected = []
    total_batches = (len(all_edges) + batch_size - 1) // batch_size

    for i in range(0, len(all_edges), batch_size):
        batch = all_edges[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        logger.info("Verifying batch %d/%d (%d edges)...", batch_num, total_batches, len(batch))

        v, r = verify_edges_with_llm(batch, batch_num, total_batches)
        verified.extend(v)
        rejected.extend(r)

        # Rate limiting for Groq API
        if batch_num < total_batches:
            time.sleep(2)

    logger.info(
        "Verification complete: %d verified, %d rejected out of %d total",
        len(verified), len(rejected), len(all_edges),
    )
    return verified, rejected


# ═══════════════════════════════════════════════════════════════════
# PHASE 4: INSERT INTO MEMGRAPH
# ═══════════════════════════════════════════════════════════════════

def insert_nodes(db, nodes_dict):
    """Insert nodes into Memgraph using MERGE."""
    inserted = 0
    for name, info in nodes_dict.items():
        label = info["label"]
        desc = info.get("description", "")
        url = info.get("source_url", "")
        try:
            db.execute(
                f"MERGE (n:{label} {{name: $name}}) "
                f"ON CREATE SET n.timestamp = $ts, n.source_count = 1, "
                f"n.description = $desc, n.source_url = $url, n.aliases = '[]' "
                f"ON MATCH SET n.source_count = n.source_count + 1, "
                f"n.description = CASE WHEN n.description IS NULL OR n.description = '' THEN $desc ELSE n.description END;",
                {"name": name, "ts": NOW, "desc": desc, "url": url},
            )
            inserted += 1
        except Exception as e:
            logger.error("Failed to insert node %s: %s", name, e)
    return inserted


def insert_edges(db, edges, node_lookup):
    """Insert edges into Memgraph using MERGE."""
    inserted = 0
    failed = 0
    for src, tgt, rel, conf in edges:
        src_label = node_lookup.get(src, {}).get("label", "Event")
        tgt_label = node_lookup.get(tgt, {}).get("label", "Event")

        try:
            # Ensure both nodes exist
            db.execute(
                f"MERGE (n:{src_label} {{name: $name}}) "
                f"ON CREATE SET n.timestamp = $ts, n.source_count = 1, n.aliases = '[]';",
                {"name": src, "ts": NOW},
            )
            db.execute(
                f"MERGE (n:{tgt_label} {{name: $name}}) "
                f"ON CREATE SET n.timestamp = $ts, n.source_count = 1, n.aliases = '[]';",
                {"name": tgt, "ts": NOW},
            )

            db.execute(
                f"MATCH (a:{src_label} {{name: $subj}}), (b:{tgt_label} {{name: $obj}}) "
                f"MERGE (a)-[r:{rel}]->(b) "
                f"ON CREATE SET r.confidence = $conf, r.sources = '[]', "
                f"r.first_seen = $ts, r.last_seen = $ts, r.version = 1, "
                f"r.status = 'active', r.source_count = 1 "
                f"ON MATCH SET r.last_seen = $ts, "
                f"r.source_count = r.source_count + 1, "
                f"r.confidence = CASE WHEN $conf > r.confidence THEN $conf ELSE r.confidence END;",
                {"subj": src, "obj": tgt, "conf": conf, "ts": NOW},
            )
            inserted += 1
        except Exception as e:
            logger.error("Failed to insert edge %s -[%s]-> %s: %s", src, rel, tgt, e)
            failed += 1

    return inserted, failed


def insert_csv_edges(db, csv_edges, node_lookup):
    """Insert CSV edges (which have source_url) with richer metadata."""
    inserted = 0
    failed = 0
    for edge in csv_edges:
        src = edge["source"]
        tgt = edge["target"]
        rel = edge["relationship"]
        conf = edge["confidence"]
        url = edge.get("source_url", "")
        src_label = node_lookup.get(src, {}).get("label", "Event")
        tgt_label = node_lookup.get(tgt, {}).get("label", "Event")

        source_entry = json.dumps([{"url": url, "snippet": ""}]) if url else "[]"

        try:
            db.execute(
                f"MERGE (n:{src_label} {{name: $name}}) "
                f"ON CREATE SET n.timestamp = $ts, n.source_count = 1, n.aliases = '[]';",
                {"name": src, "ts": NOW},
            )
            db.execute(
                f"MERGE (n:{tgt_label} {{name: $name}}) "
                f"ON CREATE SET n.timestamp = $ts, n.source_count = 1, n.aliases = '[]';",
                {"name": tgt, "ts": NOW},
            )
            db.execute(
                f"MATCH (a:{src_label} {{name: $subj}}), (b:{tgt_label} {{name: $obj}}) "
                f"MERGE (a)-[r:{rel}]->(b) "
                f"ON CREATE SET r.confidence = $conf, r.sources = $sources, "
                f"r.first_seen = $ts, r.last_seen = $ts, r.version = 1, "
                f"r.status = 'active', r.source_count = 1 "
                f"ON MATCH SET r.last_seen = $ts, "
                f"r.source_count = r.source_count + 1, "
                f"r.confidence = CASE WHEN $conf > r.confidence THEN $conf ELSE r.confidence END;",
                {"subj": src, "obj": tgt, "conf": conf, "sources": source_entry, "ts": NOW},
            )
            inserted += 1
        except Exception as e:
            logger.error("Failed to insert CSV edge %s -[%s]-> %s: %s", src, rel, tgt, e)
            failed += 1

    return inserted, failed


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    logger.info("=" * 70)
    logger.info("KNOWLEDGE GRAPH EXPANSION — Starting")
    logger.info("=" * 70)

    # ── Phase 1: Load CSV data ──
    logger.info("\n📂 Phase 1: Loading CSV data...")
    csv_nodes, csv_edges = load_csv_data()

    # ── Phase 2: Generate new knowledge ──
    logger.info("\n🧠 Phase 2: Generating domain knowledge...")

    all_generated_nodes = {}
    generators = [
        ("Geopolitics", generate_geopolitics_nodes),
        ("Economics", generate_economics_nodes),
        ("Defense", generate_defense_nodes),
        ("Technology", generate_technology_nodes),
        ("Climate", generate_climate_nodes),
        ("Society", generate_society_nodes),
        ("Supplementary", generate_supplementary_nodes),
    ]

    for domain, gen_fn in generators:
        nodes = gen_fn()
        for name, label, desc in nodes:
            all_generated_nodes[name.lower()] = {
                "name": name.lower(),
                "label": label,
                "description": desc,
                "source_url": "",
            }
        logger.info("  %s: %d nodes generated", domain, len(nodes))

    # Merge CSV nodes with generated nodes (CSV takes priority for descriptions/urls)
    combined_nodes = {**all_generated_nodes, **csv_nodes}
    logger.info("Total unique nodes: %d (CSV: %d, Generated: %d, Combined: %d)",
                len(csv_nodes) + len(all_generated_nodes),
                len(csv_nodes), len(all_generated_nodes), len(combined_nodes))

    # Generate all edges
    logger.info("\n🔗 Generating edges...")
    all_generated_edges = []
    edge_generators = [
        ("Geopolitics", generate_geopolitics_edges),
        ("Economics", generate_economics_edges),
        ("Defense", generate_defense_edges),
        ("Technology", generate_technology_edges),
        ("Climate", generate_climate_edges),
        ("Society", generate_society_edges),
        ("Supplementary", generate_supplementary_edges),
    ]

    for domain, gen_fn in edge_generators:
        edges = gen_fn()
        all_generated_edges.extend(edges)
        logger.info("  %s: %d edges generated", domain, len(edges))

    logger.info("Total generated edges: %d", len(all_generated_edges))
    logger.info("Total CSV edges: %d", len(csv_edges))

    # ── Phase 3: LLM Verification ──
    logger.info("\n🔍 Phase 3: LLM verification of generated edges...")
    verified_edges, rejected_edges = verify_all_edges(all_generated_edges)

    # Save verification results
    verification_log = {
        "timestamp": NOW,
        "total_generated_edges": len(all_generated_edges),
        "verified": len(verified_edges),
        "rejected": len(rejected_edges),
        "rejected_details": [
            {"source": e[0], "target": e[1], "relationship": e[2], "confidence": e[3]}
            for e in rejected_edges
        ],
    }
    with open(DATA_DIR / "verification_log.json", "w") as f:
        json.dump(verification_log, f, indent=2)
    logger.info("Verification log saved to data/verification_log.json")

    # ── Phase 4: Insert into Memgraph ──
    logger.info("\n💾 Phase 4: Inserting into Memgraph...")
    db = get_memgraph()

    # Create constraints and indexes first
    logger.info("Creating constraints and indexes...")
    create_constraints(db)
    create_indexes(db)

    # Insert all nodes
    logger.info("Inserting %d nodes...", len(combined_nodes))
    nodes_inserted = insert_nodes(db, combined_nodes)
    logger.info("Nodes inserted: %d", nodes_inserted)

    # Insert CSV edges (with source URLs)
    logger.info("Inserting %d CSV edges...", len(csv_edges))
    csv_ins, csv_fail = insert_csv_edges(db, csv_edges, combined_nodes)
    logger.info("CSV edges: %d inserted, %d failed", csv_ins, csv_fail)

    # Insert verified generated edges
    logger.info("Inserting %d verified generated edges...", len(verified_edges))
    gen_ins, gen_fail = insert_edges(db, verified_edges, combined_nodes)
    logger.info("Generated edges: %d inserted, %d failed", gen_ins, gen_fail)

    # ── Final Summary ──
    logger.info("\n" + "=" * 70)
    logger.info("KNOWLEDGE GRAPH EXPANSION — Complete!")
    logger.info("=" * 70)

    # Get final counts
    result = list(db.execute_and_fetch("MATCH (n) RETURN count(n) AS cnt;"))
    total_nodes = result[0]["cnt"] if result else 0
    result = list(db.execute_and_fetch("MATCH ()-[r]->() RETURN count(r) AS cnt;"))
    total_edges = result[0]["cnt"] if result else 0

    logger.info("Final graph: %d nodes, %d edges", total_nodes, total_edges)
    logger.info("  Nodes inserted this run: %d", nodes_inserted)
    logger.info("  CSV edges inserted: %d (failed: %d)", csv_ins, csv_fail)
    logger.info("  Generated edges inserted: %d (failed: %d)", gen_ins, gen_fail)
    logger.info("  Edges rejected by LLM: %d", len(rejected_edges))

    # Save updated snapshot
    from src.graph.memgraph_init import graph_snapshot
    snap = graph_snapshot(db)
    with open(DATA_DIR / "graph_snapshot.json", "w") as f:
        json.dump(snap, f, indent=2)
    logger.info("Graph snapshot saved to data/graph_snapshot.json")

    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "nodes_inserted": nodes_inserted,
        "csv_edges_inserted": csv_ins,
        "generated_edges_inserted": gen_ins,
        "edges_rejected_by_llm": len(rejected_edges),
    }


if __name__ == "__main__":
    result = main()
    print("\n" + json.dumps(result, indent=2))
