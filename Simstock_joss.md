---
title: 'SimStock: An Urban building energy modelling platform for complex urban neighbourhoods'
tags:
  - 
authors:
  - name: Ivan Korolija
    orcid: 0000-0000-0000-0000
    affiliation: "2" 
  - name: Oliver Smith
    orcid: 0000-0000-0000-0000
    affiliation: "2" 
  - name: Shyam Amrith
    orcid: 0000-0000-0000-0000
    affiliation: "2"
  - name: Pamela Fennell
    orcid: 0000-0000-0000-0000
    affiliation: "2" 
  - name: Paul Ruyssevelt
    orcid: 0000-0000-0000-0000
    affiliation: "2" 
  
affiliations:
 - name: UCL Institute for Environmental Design and Engineering, United Kingdom
   index: 1
 - name: UCL Energy Institute, United Kingdom
   index: 2

date:   30 March 2026
bibliography: JOSS_references.bib



# Summary

Urban Building Energy Models (UBEMs) play a crucial role in addressing the challenges of urbanisation and climate change by facilitating informed decision-making regarding energy efficiency interventions and policies. However, many UBEMs sacrifice granularity in order to reduce computational burden, excluding the messy detail of complex urban environments in order to simplify data collection and processing. This paper introduces SimStock, an open-source software tool designed to streamline the modelling process for complex, mixed-use urban areas. SimStock offers a comprehensive workflow encompassing data handling, pre-processing, model creation and simulation. The platform enables users to integrate diverse datasets, delineate thermal zones, conduct thermal simulations via EnergyPlus, and analyse detailed outputs down to individual thermal zones. SimStock’s usability and interpretability of data is enhanced by a dedicated QGIS plug-in that facilitates visualisation and analysis of simulation results.

# Statement of need

`Simstock` represents a departure from traditional archetype-based approaches, representing the true geometry of a neighbourhood and allowing for the nuanced representation of mixed-use buildings across large urban areas. While conventional methods may cluster buildings into a limited set of types, they often fail to capture the intricate complexities within and between mixed-use structures. SimStock, on the other hand, offers a solution by accommodating the diverse combinations of different uses within individual buildings and incorporating a spatially-explicit geometric model. This capability is crucial for addressing key use-cases, particularly in the design of interventions where a myriad of factors influenced by usage- type and interactions within the same building must be considered.

# State of the field                                                                                                                  

As Hong et al. [@hong_ten_2020] highlight: urban energy analysis is a complex, multi-scale, multi-sector challenge. Urban building energy models (UBEMs) are numerical simulations of the performance of groups of buildings, usually co-located. UBEMs aim to assess the aggregated dynamics of the group of buildings and, to differing extents, to take account of the effects each building has on its surroundings. While tools such as TEASER [@remmen_teaser:_2018], CEA [@fonseca_city_2016], OpenIDEAS [@baetens_openideas_2015] and CitySim [@robinson_citysim:_2009] are well established, the underlying Resistor-Capacitor models which typically treat each building as a single thermal zone are less reliable for predicting transient effects, making them unsuitable for assessing peak electrical loads - an increasingly important use case for UBEMs. A range of UBEMs which are based on bottom-up building physics models and incorporate detailed multi-zone models and full dynamic thermal simulation are available: In common with `SimStock`, most of these tools use EnergyPlus [@crawley_energyplus_2001] as the underlying simulation engine. However, UMI requires a Rhino licence, CityBES [@chen_automatic_2017] is a web-based tool which can only be used for a select list of cities and URBANopt [@kontar_urbanopt_2020] is not publicly available. As a result there is a clear need for an open-source tool which incorporates these capabilities. A particular aim of the developers has been to ensure that use of the tool is not restricted to users in developed cities in the global North with access to expensive user licences and carefully curated datasets.

# Software design

`SimStock`'s design philosophy is based on three core principles: (1) to provide an open source user-friendly, platform-agnostic UBEM tool, (2) to use the DOE's EnergyPlus simulation engine for energy outputs, and (3) provide a flexible and streamlined process for data assembly. It offers both programmatic and spreadsheet-based interfaces, catering to users with varying technical expertise levels and accommodating regional differences in data availability and structure. 

Simstock reads in geographical data, performs some geometric simplification steps, creates EnergyPlus idf objects, and then finally runs an EnergyPlus simulation. Simstock also provides a convenient interface to modify EnergyPlus settings such as materials, constructions, and schedules.

Simstock is structured around two objects: the SimstockDataframe and the IDFmanager. The SimstockDataframe is an extension of a Pandas Dataframe. It allows data to be read in from a variety of formats. It also performs geometric simplification on the data. The SimstockDataframe also contains the EnergyPlus settings, allowing easy manipulation of materials etc. Once these settings have been set, and any geometrical simplification performed, the IDFmanager then creates the necessary thermal zones from the SimstockDataframe. The IDFmanager can also be used to run an EnergyPlus simulation.

# Research impact statement

`SimStock` has been under continuous development since 2013. Amongst other applications, `Simstock` has been used to evaluate retrofit options in a historic city centre in France [@claude_evaluating_2019], explore the impact of input uncertainty on model outcomes in London [@fennell_comparison_2021] evaluate thermal comfort in informal settlements in Lima [@oraiopoulos_reducing_2024] and explore development pathways in Ahmedabad [@mathur_assessing_2021].`Simstock` is a core component of - a core component of the Modelling Platform for Schools [@schwartz_modelling_2022], used to evaluate London school-building stock climate resilience [@schwartz_school_2024] and has been used as a teaching tool [@fennell_developing_2023], to support the development of a stock-level optimisation methodology [@amrith_optimising_2025], to evaluate smart-energy transition pathways [@kourgiozou_development_2023] and predict district heating/cooling energy demand [@al-saegh_investigating_2025] of a university campus, to develop a methodology for planning, modelling, and evaluating renewable energy communities with a focus on urban contexts [@barone_planning_2024], to assess the impact of the future climate on the performance of retrofit strategies in Beijing, China [@deng_simulation-based_2023] and to model domestic, commercial and industrial heating/electricity demand for the Scottish islands [@matthew_time-use_2023].


Since its initial release in September 2023, the Simstock QGIS plugin has received 4,925 total downloads as of March 2026.
[include something about the number of downloads here]


# AI usage disclosure

No generative AI tools were used in the development of this software, the writing of this manuscript, or the preparation of supporting materials.

# Acknowledgements

We acknowledge contributions from Steve Evans and Rob Liddiard to support data processing for the UK, CEPT University, Ahmedabad, hosts of the first teaching initiatives using `SimSock`. Computational resources have been provided via UCL Research Computing Platforms (Legion@UCL, Myriad@UCL). Work on this paper is supported by the iNUMBER project, [grant number EP/R008620/1] and Engineering and Physical Sciences Research Council (EPSRC) Research Councils UK (RCUK) Centre for Energy  Epidemiology grant EP/K011839/1.

# References
