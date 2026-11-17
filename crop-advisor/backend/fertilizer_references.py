"""Small, source-checked reference library. Never infer a soil-adjusted dose.

Rates are fertilizer nutrients N/P2O5/K2O, not elemental soil-test readings.
The source prefers site-specific soil-test recommendations to blanket rates.
"""
RICE='https://agritech.tnau.ac.in/agriculture/agri_main_feild_%20InOrganic_biofertilizers_Rice.html'
COTTON='https://agritech.tnau.ac.in/CropProduction/Fibre%20crops/fibrecrops_cotton.html'
PROFILES=[
    {'id':'tn_rice_short_other','crop':'rice','state':'Tamil Nadu',
     'label':'Rice: short duration, dry season, other Tamil Nadu tracts',
     'conditions':'Short-duration rice in the dry season; excludes Cauvery delta and Coimbatore tract.',
     'nutrients_kg_ha':{'N':120,'P2O5':40,'K2O':40},
     'schedule':'N and K: four equal splits at basal, tillering, panicle initiation and heading. P: basal incorporation.',
     'source_url':RICE},
    {'id':'tn_rice_wet_medium_long','crop':'rice','state':'Tamil Nadu',
     'label':'Rice: medium/long duration, wet season, Tamil Nadu',
     'conditions':'Medium- or long-duration wet-season rice; not a hybrid or low-N-responsive cultivar reference.',
     'nutrients_kg_ha':{'N':150,'P2O5':50,'K2O':50},
     'schedule':'N and K: four equal splits at basal, tillering, panicle initiation and heading. P: basal incorporation.',
     'source_url':RICE},
    {'id':'tn_cotton_irrigated_varieties','crop':'cotton','state':'Tamil Nadu',
     'label':'Cotton: specified irrigated varieties, Tamil Nadu',
     'conditions':'Irrigated MCU 5, MCU 5 VT, MCU 12, MCU 13, Suvin or SVPR 2. Not rainfed or hybrid cotton.',
     'nutrients_kg_ha':{'N':80,'P2O5':40,'K2O':40},
     'schedule':'Half N/K and all P2O5 at basal; remaining N/K at 40–45 days after sowing for these varieties.',
     'source_url':COTTON}
]

def reference_for(crop,state,profile_id,basis,conditions_confirmed):
    if not profile_id:
        return {'status':'not_selected','message':'Select a matching regional reference to view published guidance. No dose is inferred from the CSV.'}
    profile=next((p for p in PROFILES if p['id']==profile_id),None)
    if not profile or profile['crop']!=crop or profile['state'].casefold()!=state.strip().casefold():
        raise ValueError('Reference does not match the selected crop and state')
    if basis!='confirmed_available_kg_ha' or not conditions_confirmed:
        return {'status':'confirmation_needed','message':'Confirm laboratory available elemental N/P/K units and that the selected cultivation conditions match before viewing this regional plan.'}
    return {'status':'reference_only',**profile,'checked_on':'2026-11-17',
            'note':'Published blanket reference, not a soil-adjusted prescription. Prefer a local soil-test plan. Soil P/K readings and fertilizer P2O5/K2O rates use different bases; do not subtract them. No product quantities are calculated.'}
