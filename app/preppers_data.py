"""Preppers directory data (tab "🎒 Preppers", served by preppers.py). Hand-curated, research-only, no affiliate links.
Row format: name | url | category | tags | region/ships-to | price tier | rubric scores | note
Rubric scores = 5 digits, each 0-2: reputation/longevity, product quality & independent reviews, value, transparency/warranty, availability.
Rating (0-10) = sum. Notes are modest and based on each company's own pages or well-known public information."""
CATS = [
 ("water", "Water", "💧"), ("food", "Food", "🥫"), ("medical", "Medical & first aid", "⛑"),
 ("power", "Power & energy", "🔋"), ("comms", "Comms & radio", "📡"), ("ammo", "Ammo & firearm accessories", "🎯"),
 ("ranges", "Ranges & training", "🏹"), ("camping", "Camping, shelter & gear", "⛺"), ("tools", "Tools, EDC & lighting", "🔪"),
 ("bags", "Bags & bug-out", "🎒"), ("sanitation", "Sanitation & hygiene", "🧼"), ("heat", "Heating, cooking & fuel", "🔥"),
 ("security", "Security & home hardening", "🛡"), ("docs", "Documents & finances", "📁"), ("special", "Pets, kids, elders & meds", "🐾"),
 ("seeds", "Seeds, garden & livestock", "🌱"), ("nav", "Navigation & maps", "🧭"), ("training", "Knowledge & official guidance", "🎓"),
 ("community", "Community networks", "🤝"), ("books", "Books & free manuals", "📚"),
]
ROWS = r"""
Sawyer water filters|https://www.sawyer.com/category/water-filtration|water|filters,portable,hollow-fiber|US · ships worldwide|$|22222|Squeeze and Mini hollow-fiber filters; light, cheap and widely used by hikers and aid groups.
LifeStraw|https://lifestraw.com/collections/emergency-prep|water|filters,portable,straw|Global|$|22212|Personal straw and bottle filters plus family-size gravity units; easy for kids and go-bags.
Katadyn|https://katadyn.com/collections/filter|water|filters,purification,tablets|Global (Swiss)|$$|22122|Long-running Swiss maker of pump filters, gravity filters and Micropur tablets.
MSR water treatment (Cascade Designs)|https://cascadedesigns.com/collections/water-treatment|water|filters,purification,gravity|US · Global|$$|22122|Guardian purifier and gravity filters from Cascade Designs; field-serviceable.
Platypus GravityWorks|https://www.platy.com|water|filters,gravity,storage|US · Global|$$|21122|Hands-free gravity filter kits and collapsible water reservoirs.
Grayl|https://grayl.com|water|purification,bottle|US · Global|$$|12122|Press-style purifier bottle claimed to remove viruses as well as bacteria; good for travel bags.
Berkey (Big Berkey)|https://www.berkeywater.com/|water|filters,gravity,countertop|US|$$$|11111|Popular countertop gravity filter; regulatory and stock issues in recent years, so check current availability and certifications.
Aquatabs|https://www.aquatabs.com|water|purification,tablets|Global|$|22212|Chlorine (NaDCC) purification tablets used by relief agencies; tiny and long-lasting.
Potable Aqua|https://pharmacalway.com/potableaqua/|water|purification,tablets|US · Global|$|21212|Iodine and chlorine dioxide tablets; compact backup treatment for go-bags.
WaterBrick|https://waterbrick.org|water|storage,containers|US · Global|$$|21111|Stackable 3.5 gal food-grade containers that fit under beds and in closets.
Reliance Aqua-Tainer|https://www.relianceproducts.com|water|storage,containers,sanitation|US · CA|$|21222|7 gal Aqua-Tainer jugs and Luggable Loo bucket toilets; cheap, sold at big-box stores.
Scepter containers|https://www.scepter.com|water|storage,fuel cans,containers|US · CA · Global|$|21112|Military-style water and fuel containers.
WaterBOB|https://www.waterbob.com|water|storage,bathtub|US|$|11211|Bathtub bladder that holds about 100 gal when you have warning of an outage or storm.
EPA: emergency disinfection of drinking water|https://www.epa.gov/ground-water-and-drinking-water/emergency-disinfection-drinking-water|water|guide,boiling,bleach|Free · US guidance|Free|22222|Official boil and bleach ratios for making water safe.
Mountain House|https://mountainhouse.com|food|freeze-dried,long-term|US · some intl|$$|22122|Freeze-dried meals with a 30-year taste guarantee on many pouches and cans; long track record.
Augason Farms|https://augasonfarms.com|food|long-term,bulk,buckets|US|$$|21112|Bulk #10 cans and buckets of staples (oats, rice, powdered milk) widely sold at big-box stores.
ReadyWise|https://readywise.com|food|freeze-dried,buckets|US|$$|11111|Bucket kits; compare calories per serving, not just "servings".
Valley Food Storage|https://valleyfoodstorage.com|food|freeze-dried,long-term|US|$$|11111|Long-term meal kits; read the ingredient and calorie panels.
Legacy Food Storage|https://www.legacyfoodstorage.com|food|freeze-dried,long-term|US|$$|11111|Long-term meal buckets; check calories per serving.
Peak Refuel|https://peakrefuel.com|food|freeze-dried,high-protein|US|$$|12112|Higher-protein freeze-dried meals aimed at hunters and hikers.
Backpacker's Pantry|https://www.backpackerspantry.com|food|freeze-dried,camping|US · CA|$$|21112|Freeze-dried trail meals with vegetarian and gluten-free options.
Thrive Life|https://www.thrivelife.com|food|freeze-dried,ingredients|US · CA|$$|11111|Freeze-dried single ingredients for cooking from storage.
Be Prepared (Emergency Essentials)|https://beprepared.com|food|long-term,kits,bulk|US|$$|21111|Long-running Utah storage retailer for food, water barrels and kits.
Church Home Storage Centers|https://providentliving.churchofjesuschrist.org/food-storage?lang=eng|food|bulk,canned,guides|US · some intl · open to all|$|22222|Low-cost wheat, rice, beans and oats in long-life cans, plus free storage guides; open to the public.
Costco emergency food & kits|https://www.costco.com/emergency-kits-supplies.html|food|bulk,kits,canned|US · CA · UK · AU|$$|22212|Bulk emergency food buckets and kits; membership pricing.
Sam's Club emergency supplies|https://www.samsclub.com/s/emergency%20food|food|bulk,canned|US|$$|21212|Bulk canned goods and emergency food buckets; membership pricing.
Walton Feed|https://www.waltonfeed.com|food|bulk,grains|US|$$|11111|Old-line bulk grain and bean supplier for long-term storage.
Datrex emergency rations|https://www.datrex.com|food|ration bars,go-bag|US · Global|$|21212|US Coast Guard-approved 3,600 kcal ration bars with a 5-year shelf life; for go-bags and cars.
SOS Food Lab ration bars|https://www.sosfoodlab.com|food|ration bars,go-bag|US · Global|$|21212|ER Emergency Ration bars; Coast Guard-approved, 5-year shelf life.
Expedition Foods (UK)|https://www.expeditionfoods.com|food|freeze-dried,high-calorie|UK · EU · Global|$$|21112|UK freeze-dried meals, including 800–1,000 kcal high-energy pouches.
Ball canning|https://www.ballmasonjars.com|food|canning,jars,preserving|US · CA|$|22222|Jars, lids and tested recipes for home canning.
Harvest Right|https://harvestright.com|food|freeze dryer,home|US · Global|$$$|12011|Home freeze-dryer machines; expensive and loud but let you preserve your own food.
National Center for Home Food Preservation|https://nchfp.uga.edu|food|canning,guide,safety|Free · Global|Free|22222|University of Georgia's research-tested canning and drying guidance; avoids botulism mistakes.
USDA: food safety in emergencies|https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/emergencies|food|guide,power outage|Free · US guidance|Free|22222|What to keep or toss after a power outage or flood.
North American Rescue|https://www.narescue.com|medical|trauma,IFAK,tourniquets|US · Global|$$|22122|Major supplier of military trauma gear (CAT tourniquets, IFAKs); buy authentic, not knock-offs.
Rescue Essentials|https://www.rescue-essentials.com|medical|trauma,IFAK,kits|US|$$|22112|Trauma and tactical-medic supplies and kits.
Chinook Medical Gear|https://www.chinookmed.com|medical|trauma,expedition,kits|US|$$|22112|Expedition and austere-medicine kits and supplies.
Dark Angel Medical|https://www.darkangelmedical.com|medical|trauma,kits,training|US|$$|22112|Compact bleeding-control kits plus trauma classes.
My Medic|https://mymedic.com|medical|kits,first aid|US|$$|11112|Bright, well-organized first-aid kits; compare contents to price.
Adventure Medical Kits|https://www.adventuremedicalkits.com|medical|kits,first aid,outdoor|US · Global|$|22212|Outdoor first-aid kits sized by trip length and group.
Stop the Bleed|https://www.stopthebleed.org|medical|training,bleeding control|Free · US · Global|Free|22222|Free/low-cost bleeding-control classes; the single most useful trauma skill.
Red Cross first aid classes|https://www.redcross.org/take-a-class/first-aid|medical|training,CPR,first aid|US|$|22222|First aid, CPR and AED classes in person and online.
American Heart Association CPR|https://cpr.heart.org/en/courses|medical|training,CPR|US · Global|$|22222|CPR and BLS courses with a class finder.
St John Ambulance (UK)|https://shop.sja.org.uk/collections/first-aid-courses|medical|training,first aid|UK|$|22222|UK first-aid courses for individuals and workplaces.
St John Ambulance Canada|https://www.sja.ca|medical|training,first aid|CA|$|22222|Canadian first-aid and CPR training.
St John Ambulance Australia|https://www.stjohn.org.au|medical|training,first aid,kits|AU|$|22222|Australian first-aid training and kits.
Wilderness Medical Associates|https://www.wildmed.com|medical|training,wilderness|US · CA · Global|$$|22122|WFA/WFR courses for when help is hours or days away.
NOLS Wilderness Medicine|https://www.nols.edu/en/wilderness-medicine|medical|training,wilderness|US · Global|$$|22122|Wilderness First Aid and First Responder courses.
FDA: potassium iodide (KI) FAQ|https://www.fda.gov/drugs/bioterrorism-and-drug-preparedness/frequently-asked-questions-potassium-iodide-ki|medical|nuclear,guide|Free · US guidance|Free|22222|When KI helps (and doesn't) after a radiation release.
Jackery|https://www.jackery.com|power|power station,solar|US · Global|$$$|21112|Portable power stations and folding panels for phones, CPAPs and small appliances.
EcoFlow|https://us.ecoflow.com|power|power station,solar,home backup|US · Global|$$$|22112|Power stations from small to whole-home backup; fast AC charging.
Anker SOLIX|https://www.ankersolix.com/collections/power-stations|power|power station,solar|US · Global|$$$|22112|Anker's power-station line; LiFePO4 models with long warranties.
Bluetti|https://www.bluettipower.com|power|power station,solar|US · Global|$$$|12112|LiFePO4 power stations and expansion batteries.
Goal Zero|https://www.goalzero.com|power|power station,solar,small|US · Global|$$|21111|Early leader in portable solar; small power banks and Yeti stations.
Renogy|https://www.renogy.com|power|solar,batteries,DIY|US · Global|$$|21212|Panels, charge controllers and batteries for DIY solar.
Battle Born Batteries|https://battlebornbatteries.com|power|batteries,LiFePO4,DIY|US|$$$|22021|US-assembled LiFePO4 batteries with a 10-year warranty.
Honda generators|https://powerequipment.honda.com/generators|power|generator,inverter|US · Global|$$$|22022|Quiet, reliable inverter generators; the long-time benchmark.
Champion Power Equipment|https://www.championpowerequipment.com|power|generator,dual-fuel|US · CA|$$|21212|Value dual-fuel (gas/propane) generators.
Generac|https://www.generac.com|power|generator,standby,home|US · Global|$$$|21112|Whole-home standby generators; installed by dealers.
CPSC: portable generator safety|https://www.cpsc.gov/Safety-Education/Safety-Education-Centers/Portable-Generators|power|safety,carbon monoxide,guide|Free · US guidance|Free|22222|Carbon monoxide kills people after storms; keep generators outside and away from windows.
ARRL: getting licensed|https://www.arrl.org/getting-licensed|comms|ham,license,training|Free · US|Free|22222|How to get a US amateur radio license; the national ham association.
HamStudy|https://hamstudy.org|comms|ham,license,training|Free · Global|Free|22222|Free practice exams for US ham licenses.
FCC: GMRS licensing|https://www.fcc.gov/wireless/bureau-divisions/mobility-division/general-mobile-radio-service-gmrs|comms|GMRS,license|Free · US|$|22222|One license covers your family for 10 years; no exam.
RSGB: get started (UK)|https://rsgb.org/main/get-started-in-amateur-radio|comms|ham,license|UK|Free|22222|UK amateur radio licensing and training.
Radio Amateurs of Canada|https://www.rac.ca|comms|ham,license|CA|Free|22222|Canadian ham radio association and licensing info.
Wireless Institute of Australia|https://www.wia.org.au|comms|ham,license|AU|Free|22222|Australian amateur radio association.
Midland radios|https://midlandusa.com|comms|GMRS,NOAA,two-way|US · CA|$$|22212|GMRS, FRS and NOAA weather-alert radios.
Motorola Talkabout|https://www.motorolasolutions.com/en_us/products/two-way-radios/consumer-two-way-radios.html|comms|FRS,two-way|US · Global|$|21212|License-free FRS walkie-talkies for families.
Baofeng (official)|https://baofengtech.com|comms|ham,GMRS,handheld|US · Global|$|11212|Very cheap handhelds; most models need a ham or GMRS license to transmit legally.
Uniden scanners|https://www.uniden.com|comms|scanner,CB,weather|US · Global|$$|21212|Police/fire scanners and CB radios for listening to what's happening.
NOAA Weather Radio|https://www.weather.gov/nwr|comms|NOAA,alerts,guide|Free · US|Free|22222|National Weather Service alert broadcasts; find your local transmitter.
C. Crane|https://ccrane.com|comms|AM/FM,weather radio,shortwave|US|$$|22122|Sensitive AM/FM/weather radios with strong customer service.
Eton (Red Cross radios)|https://etoncorp.com|comms|hand-crank,weather radio|US · Global|$|21212|Hand-crank and solar weather radios that charge phones.
Garmin inReach|https://www.garmin.com/en-US/c/outdoor-recreation/satellite-communicators|comms|satellite,SOS,messaging|Global|$$|22112|Satellite texting and SOS anywhere; needs a subscription.
ZOLEO|https://www.zoleo.com|comms|satellite,SOS,messaging|Global|$$|12112|Satellite messenger on the Iridium network; needs a plan.
Starlink|https://www.starlink.com|comms|satellite,internet|Global|$$$|22112|Satellite internet that kept working in many disasters; needs power and a monthly plan.
Meshtastic|https://meshtastic.org|comms|mesh,off-grid,open source|Free · Global|$|12222|Open-source off-grid text mesh on cheap LoRa radios; no license needed.
goTenna|https://gotenna.com|comms|mesh,off-grid|US|$$|11011|Mesh texting devices; product line has shifted toward government users.
RepeaterBook|https://www.repeaterbook.com|comms|ham,repeaters,directory|Free · Global|Free|21222|Find local ham and GMRS repeaters.
FEMA IPAWS (public alerts)|https://www.fema.gov/emergency-managers/practitioners/integrated-public-alert-warning-system|comms|alerts,guide|Free · US|Free|22222|How Wireless Emergency Alerts and EAS reach your phone and radio.
MidwayUSA|https://www.midwayusa.com|ammo|retailer,ammo,accessories,reloading|US|$$|22212|Large online shooting and reloading retailer with good customer service.
Brownells|https://www.brownells.com|ammo|retailer,parts,accessories|US · some intl|$$|22212|Gunsmithing parts, magazines and accessories since 1939.
Lucky Gunner|https://www.luckygunner.com|ammo|retailer,ammo|US|$$|22212|Ammo retailer known for clear stock info and independent ammo tests.
Ammo.com|https://ammo.com|ammo|retailer,ammo|US|$$|11212|Online ammo marketplace with bulk listings.
Sportsman's Warehouse|https://www.sportsmans.com|ammo|retailer,outdoor,ammo|US|$$|21112|Outdoor chain selling ammo, optics and camping gear.
Bass Pro Shops|https://www.basspro.com|ammo|retailer,outdoor,ammo|US · CA|$$|21212|Big outdoor chain; ammo, safes and camping gear.
Cabela's|https://www.cabelas.com|ammo|retailer,outdoor,ammo|US · CA|$$|21212|Sister chain to Bass Pro.
Academy Sports + Outdoors|https://www.academy.com|ammo|retailer,outdoor|US|$|21212|Southern and Midwest chain with low ammo and camping prices.
Hornady|https://www.hornady.com|ammo|manufacturer,ammo,reloading|US · Global|$$|22112|US ammunition and reloading maker; good load data.
SAAMI|https://saami.org|ammo|safety,storage,guide|Free · US|Free|22222|Industry standards body; safe ammunition storage and handling guidance.
Project ChildSafe (NSSF)|https://projectchildsafe.org|ammo|safety,storage,locks|Free · US|Free|22222|Safe-storage guidance and free cable locks through local partners.
NRA-ILA state gun laws|https://www.nraila.org/gun-laws|ammo|laws,reference|Free · US|Free|21222|Gun-rights group's state-by-state law summaries; compare with official state sources.
Giffords state gun laws|https://giffords.org/lawcenter/gun-laws/browse-state-gun-laws|ammo|laws,reference|Free · US|Free|21222|Gun-safety group's state law summaries; compare with official state sources.
NSSF WhereToShoot|https://www.wheretoshoot.org|ranges|range finder,directory|Free · US · CA|Free|22222|The largest US directory of public and private shooting ranges, by location.
NRA firearm training|https://firearmtraining.nra.org|ranges|training,courses,finder|US|$|22212|Find NRA-certified basic pistol, rifle and safety courses.
USCCA training|https://www.usconcealedcarry.com/training|ranges|training,courses,concealed carry|US|$$|21112|Concealed-carry and home-defense classes with a class finder.
IHEA-USA hunter education|https://www.ihea-usa.org/hunter-education|ranges|hunter ed,state agencies|Free · US · CA|Free|22222|Links to every state and province's hunter-ed program.
hunter-ed.com|https://www.hunter-ed.com|ranges|hunter ed,online|US · CA|$|22212|Official online hunter-ed courses approved by many states.
Civilian Marksmanship Program|https://thecmp.org|ranges|marksmanship,clubs,training|US|$|22212|Congressionally chartered rifle marksmanship and safety program.
Project Appleseed|https://appleseedinfo.org|ranges|marksmanship,clinics|US|$|21222|Low-cost rifle marksmanship clinics with a history lesson.
USPSA club finder|https://uspsa.org|ranges|clubs,competition|US|$|21212|Practical shooting clubs; matches build safe gun handling under time pressure.
IDPA|https://www.idpa.com|ranges|clubs,competition|US · Global|$|21212|Defensive-pistol matches at local clubs.
British Shooting|https://www.britishshooting.org.uk|ranges|clubs,UK|UK|$|21212|UK governing body for target shooting; club finder.
NRA UK (Bisley)|https://nra.org.uk|ranges|ranges,clubs,UK|UK|$|21212|National Shooting Centre at Bisley and UK club network.
RCMP: firearms safety courses|https://rcmp.ca/en/firearms|ranges|licensing,training,Canada|CA|Free|22222|Canadian firearms licensing (PAL) and the required safety course.
SSAA (Australia)|https://ssaa.org.au|ranges|clubs,ranges,Australia|AU|$|21212|Sporting Shooters' Association of Australia: ranges and clubs.
REI camping & hiking|https://www.rei.com/c/camping-and-hiking|camping|retailer,tents,sleeping|US|$$|22122|Co-op with a generous return policy and solid how-to articles.
Backcountry|https://www.backcountry.com|camping|retailer,outdoor|US|$$|21112|Large online outdoor retailer.
Sportsman's Guide|https://www.sportsmansguide.com|camping|retailer,surplus,budget|US|$|11212|Military surplus and budget outdoor gear.
Coleman|https://www.coleman.com|camping|tents,stoves,lanterns|Global|$|21212|Affordable tents, propane stoves and lanterns found everywhere.
Kelty|https://www.kelty.com|camping|tents,sleeping bags,packs|US · Global|$$|21212|Value tents, bags and packs.
Big Agnes|https://www.bigagnes.com|camping|tents,sleeping|US · Global|$$$|22112|Lightweight tents and sleeping systems.
Snugpak (UK)|https://www.snugpak.com|camping|sleeping bags,insulation,UK|UK · Global|$$|22112|British sleeping bags and insulated clothing used by militaries.
SOL (Survive Outdoors Longer)|https://www.surviveoutdoorslonger.com|camping|emergency bivy,blankets|US · Global|$|21222|Emergency bivvies and blankets that weigh ounces; great for car and go-bags.
MEC (Canada)|https://www.mec.ca|camping|retailer,Canada|CA|$$|21112|Canada's big outdoor retailer.
Decathlon|https://www.decathlon.com|camping|retailer,budget,Europe|Global · EU · UK|$|11212|Budget outdoor gear sold across Europe and worldwide.
Cotswold Outdoor (UK)|https://www.cotswoldoutdoor.com|camping|retailer,UK|UK · IE|$$|21112|UK outdoor retailer.
Anaconda (AU)|https://www.anacondastores.com|camping|retailer,Australia|AU|$$|11112|Australian camping and outdoor chain.
Leatherman|https://www.leatherman.com|tools|multi-tool|US · Global|$$|22122|Multi-tools with a 25-year warranty.
Victorinox|https://www.victorinox.com|tools|knives,multi-tool|Global (Swiss)|$|22222|Swiss Army knives; small, legal almost everywhere, lifetime guarantee.
Morakniv|https://morakniv.se/en|tools|knives,bushcraft|Global (Swedish)|$|22222|Cheap, excellent Swedish fixed-blade knives.
Gerber|https://www.gerbergear.com|tools|knives,multi-tool|US · Global|$|11212|Budget knives and multi-tools.
Fiskars|https://www.fiskars.com|tools|axes,saws,garden|Global|$|22212|Axes, hatchets, saws and garden tools.
Gränsfors Bruk|https://www.gransforsbruk.com/en|tools|axes|Global (Swedish)|$$$|22022|Hand-forged Swedish axes built to last generations.
Estwing|https://www.estwing.com|tools|hammers,axes|US · Global|$|22212|One-piece US-made hammers and hatchets.
Light My Fire|https://www.lightmyfire.com|tools|fire starting,ferro rod|Global (Swedish)|$|21212|Ferro-rod fire starters and camp cookware.
Streamlight|https://www.streamlight.com|tools|lighting,flashlights|US · Global|$$|22122|Rugged flashlights with a limited lifetime warranty.
Fenix|https://www.fenixlighting.com|tools|lighting,headlamps|US · Global|$$|21112|Bright rechargeable flashlights and headlamps.
Black Diamond headlamps|https://www.blackdiamondequipment.com|tools|lighting,headlamps|US · Global|$|22212|Hands-free headlamps; the light you'll actually use in an outage.
Osprey|https://www.osprey.com|bags|packs,bug-out|US · Global|$$|22122|Comfortable packs with the All Mighty Guarantee repair policy.
Mystery Ranch|https://www.mysteryranch.com|bags|packs,heavy loads|US · Global|$$$|22112|Load-hauling packs designed for heavy gear.
5.11 Tactical|https://www.511tactical.com|bags|packs,EDC,clothing|US · Global|$$|21112|Tactical packs, EDC bags and work wear.
Maxpedition|https://www.maxpedition.com|bags|packs,pouches,EDC|US · Global|$$|21112|Modular bags and pouches.
GORUCK|https://www.goruck.com|bags|packs,rucks|US|$$$|21022|Very durable rucks with a lifetime guarantee.
Vanquest|https://www.vanquest.com|bags|EDC,organizers|US|$$|11121|Organizer bags and EDC pouches.
Thetford portable toilets|https://www.thetford.com|sanitation|toilet,portable|Global|$$|22112|Porta Potti portable toilets for when water or sewer fails.
Cleanwaste (WAG bags)|https://www.cleanwaste.com|sanitation|toilet,waste bags|US|$|21212|Gelling waste bags and GO Anywhere toilets.
Dr. Bronner's|https://www.drbronner.com|sanitation|soap,hygiene|US · Global|$|22212|Concentrated castile soap that covers body, dishes and laundry.
Coghlan's|https://www.coghlans.com|sanitation|camp hygiene,small gear|Global|$|11212|Cheap camp hygiene and small essentials.
CDC: hygiene and handwashing|https://www.cdc.gov/clean-hands/about/index.html|sanitation|guide,handwashing|Free · Global|Free|22222|Why handwashing prevents most illness in a disaster.
Mr. Heater|https://www.mrheater.com|heat|propane heater,indoor-safe|US · CA|$|21212|Buddy propane heaters rated for indoor use (low-oxygen shutoff); still use a CO alarm.
Camp Chef|https://www.campchef.com|heat|stoves,propane|US|$$|21112|Propane camp stoves and outdoor cooking.
Jetboil|https://www.jetboil.com|heat|stoves,backpacking|US · Global|$$|22112|Fast canister stoves for boiling water.
BioLite|https://www.bioliteenergy.com|heat|stoves,wood,lighting|US · Global|$$|11111|Wood-burning CampStove that charges devices; also lanterns.
Solo Stove|https://www.solostove.com|heat|wood stove,fire pit|US · Global|$$|21111|Wood-burning camp stoves and fire pits.
Lodge Cast Iron|https://www.lodgecastiron.com|heat|cookware,cast iron|US · Global|$|22222|Cast-iron pans and Dutch ovens that work on any fire.
Sun Oven|https://www.sunoven.com|heat|solar cooking|US · Global|$$|11111|Solar ovens that cook without fuel on sunny days.
Kidde CO alarms|https://www.kidde.com|heat|carbon monoxide,smoke alarms|US · Global|$|22212|Battery CO and smoke alarms; essential with any heater or generator.
CDC: carbon monoxide poisoning|https://www.cdc.gov/carbon-monoxide/about/index.html|heat|safety,guide|Free · Global|Free|22222|CO prevention when using heaters, stoves and generators.
NFPA: heating safety|https://www.nfpa.org/education-and-research/home-fire-safety/heating|heat|fire safety,guide|Free · Global|Free|22222|Space-heater and fuel safety tips from the fire-code body.
SimpliSafe|https://simplisafe.com|security|alarm,cellular backup|US · UK|$$|21212|DIY alarm with cellular and battery backup; no long contract.
Schlage|https://www.schlage.com|security|locks,deadbolts|US · CA|$$|22212|Grade 1 deadbolts; the cheapest real security upgrade.
Armor Concepts|https://armorconcepts.com|security|door reinforcement|US|$$|11121|Door jamb reinforcement kits against kick-ins.
First Alert|https://www.firstalert.com|security|smoke,CO,fire extinguishers|US · CA|$|22212|Smoke/CO alarms and extinguishers.
SentrySafe|https://www.sentrysafe.com|security|fire safe,documents|US · Global|$|11212|Fire and water-resistant boxes for documents.
Liberty Safe|https://www.libertysafe.com|security|gun safe,fire safe|US|$$$|11112|Large gun and fire safes; read reviews on steel gauge and fire rating.
FEMA: safe rooms|https://www.fema.gov/emergency-managers/risk-management/safe-rooms|security|tornado,hurricane,guide|Free · US|Free|22222|Building a tornado or hurricane safe room.
IBHS FORTIFIED Home|https://fortifiedhome.org|security|roof,hurricane,hail|Free · US|Free|22222|Research-based roof and wind upgrades; may lower insurance in some states.
National Neighborhood Watch|https://www.nnw.org|security|community,neighborhood|Free · US|Free|21222|Start or join a neighborhood watch through the National Sheriffs' Association.
Ready.gov: financial preparedness (EFFAK)|https://www.ready.gov/financial-preparedness|docs|documents,finances,checklist|Free · US|Free|22222|Emergency Financial First Aid Kit: which papers, accounts and cash to keep ready.
CFPB: disasters and emergencies|https://www.consumerfinance.gov/consumer-tools/disasters-and-emergencies|docs|finances,insurance,guide|Free · US|Free|22222|Protecting money, credit and insurance claims after a disaster.
IRS: disaster tax relief|https://www.irs.gov/newsroom/tax-relief-in-disaster-situations|docs|taxes,guide|Free · US|Free|22222|Deadline extensions and record replacement after declared disasters.
FloodSmart (NFIP)|https://www.floodsmart.gov|docs|flood insurance,guide|Free · US|Free|22222|Federal flood insurance; most home policies exclude flood, and there's a 30-day wait.
Bitwarden|https://bitwarden.com|docs|password manager,digital copies|Global|$|22222|Open-source password manager with encrypted attachments for document scans.
Ready.gov: pets|https://www.ready.gov/pets|special|pets,guide|Free · US|Free|22222|Pet emergency kit and evacuation planning.
ASPCA disaster preparedness|https://www.aspca.org/pet-care/general-pet-care/disaster-preparedness|special|pets,guide|Free · US|Free|22222|Pet kits, rescue stickers and finding pet-friendly shelters.
Ready.gov: kids|https://www.ready.gov/kids|special|kids,games,guide|Free · US|Free|22222|Kid-friendly games and family plans.
Ready.gov: older adults|https://www.ready.gov/older-adults|special|elderly,guide|Free · US|Free|22222|Planning for mobility, medication and support networks.
Ready.gov: people with disabilities|https://www.ready.gov/disability|special|disability,guide|Free · US|Free|22222|Planning for power-dependent devices, service animals and communication needs.
FDA: drugs after a natural disaster|https://www.fda.gov/drugs/emergency-preparedness-drugs/safe-drug-use-after-natural-disaster|special|medications,storage,guide|Free · US|Free|22222|When heat- or water-damaged medicines are unsafe, and insulin storage.
Healthcare Ready (Rx Open)|https://healthcareready.org/rxopen|special|pharmacies,medications|Free · US|Free|22222|Map of pharmacies open in disaster areas.
HealthyChildren.org: safety at home|https://www.healthychildren.org/English/safety-prevention/at-home/Pages/default.aspx|special|kids,guide|Free · US|Free|22222|American Academy of Pediatrics' safety and disaster-readiness articles for families.
Baker Creek Heirloom Seeds|https://www.rareseeds.com|seeds|heirloom,open-pollinated|US · Global|$|22212|Large catalog of heirloom, open-pollinated seed you can save.
Seed Savers Exchange|https://seedsavers.org|seeds|heirloom,nonprofit|US|$|22222|Nonprofit seed bank and catalog.
Johnny's Selected Seeds|https://www.johnnyseeds.com|seeds|vegetable,farm,tools|US · CA|$$|22122|Employee-owned seed company trusted by market farmers.
Territorial Seed|https://territorialseed.com|seeds|vegetable,garden|US|$|21212|Garden seed and supplies.
High Mowing Organic Seeds|https://www.highmowingseeds.com|seeds|organic,vegetable|US|$|21212|Organic vegetable seed.
West Coast Seeds (Canada)|https://www.westcoastseeds.com|seeds|vegetable,Canada|CA|$|21212|Canadian vegetable and herb seed.
Real Seed Catalogue (UK)|https://www.realseeds.co.uk|seeds|open-pollinated,UK|UK · EU|$|21222|Open-pollinated seed with saving instructions.
Diggers Club (AU)|https://www.diggers.com.au|seeds|heirloom,Australia|AU|$|21212|Australian heirloom seed club.
Tractor Supply|https://www.tractorsupply.com|seeds|livestock,feed,fencing|US|$$|21212|Feed, fencing, chicks and farm tools.
Murray McMurray Hatchery|https://www.mcmurrayhatchery.com|seeds|chickens,livestock|US|$|22212|Mail-order chicks since 1917.
USGS topoView|https://ngmdb.usgs.gov/topoview|nav|topo maps,free|Free · US|Free|22222|Download any USGS topo map, current or historical.
CalTopo|https://caltopo.com|nav|maps,planning,printable|US · Global|$|22222|Mapping used by search-and-rescue; print maps for offline use.
Gaia GPS|https://www.gaiagps.com|nav|maps,offline,app|Global|$$|21112|Offline topo maps on your phone.
OsmAnd|https://osmand.net|nav|offline maps,app|Free · Global|$|22222|Offline maps and navigation from OpenStreetMap data.
Organic Maps|https://organicmaps.app|nav|offline maps,app|Free · Global|Free|22222|Free offline maps without tracking.
Ordnance Survey (UK)|https://www.ordnancesurvey.co.uk|nav|topo maps,UK|UK|$|22222|Britain's national mapping agency; paper and app maps.
Natural Resources Canada topo maps|https://natural-resources.canada.ca/maps-tools-publications/maps/topographic-maps|nav|topo maps,Canada|CA|Free|22222|Canada's official topographic maps.
Suunto compasses|https://www.suunto.com|nav|compass|Global (Finnish)|$|22112|Baseplate and sighting compasses.
Cammenga|https://www.cammenga.com|nav|compass,lensatic|US|$$|22112|US military-issue lensatic compasses.
Ready.gov: build a kit|https://www.ready.gov/kit|training|kit list,official|Free · US|Free|22222|The official basic kit list and how to maintain it.
Ready.gov: make a plan|https://www.ready.gov/plan|training|family plan,official|Free · US|Free|22222|Family communication and meeting-place plan templates.
FEMA Emergency Management Institute (free courses)|https://training.fema.gov/is|training|online courses,official|Free · Global|Free|22222|Free online independent-study courses, open to anyone.
Red Cross: how to prepare|https://www.redcross.org/get-help/how-to-prepare-for-emergencies.html|training|guide,official|Free · US|Free|22222|Hazard-by-hazard preparation guides.
National Weather Service safety|https://www.weather.gov/safety|training|weather,guide,official|Free · US|Free|22222|Safety for every type of weather hazard.
National Hurricane Center: prepare|https://www.nhc.noaa.gov/prepare|training|hurricane,guide,official|Free · Atlantic/Pacific|Free|22222|Hurricane preparedness week-by-week.
Great ShakeOut (earthquakes)|https://www.shakeout.org|training|earthquake,drills|Free · Global|Free|22222|Drop, Cover, Hold On drills and earthquake guides.
The Prepared|https://theprepared.com|training|guides,gear reviews,independent|Free · Global|Free|21222|Independent, evidence-minded prepping guides and gear reviews.
UK Government: Prepare|https://prepare.campaign.gov.uk|training|official,UK|Free · UK|Free|22222|UK government advice on emergencies and kits.
Canada: Get Prepared|https://www.getprepared.gc.ca|training|official,Canada|Free · CA|Free|22222|Government of Canada 72-hour kit and hazard guides.
Australian Red Cross: Prepare|https://www.redcross.org.au/prepare|training|official,Australia|Free · AU|Free|22222|RediPlan and emergency guidance for Australia.
NZ: Get Ready|https://getready.govt.nz|training|official,New Zealand|Free · NZ|Free|22222|New Zealand's official emergency guidance.
Finland: 72 hours|https://72tuntia.fi/en|training|official,Finland,EU|Free · EU|Free|22222|Finland's 72-hour home preparedness program.
Germany: BBK (civil protection)|https://www.bbk.bund.de/DE/Home/home_node.html|training|official,Germany,EU|Free · EU|Free|22222|German federal civil protection advice and supply checklists.
FEMA CERT (Community Emergency Response Teams)|https://www.ready.gov/cert|community|volunteer,training,official|Free · US|Free|22222|Free training in light search and rescue, triage and fire safety.
ARRL ARES (emergency ham radio)|https://www.arrl.org/ares|community|ham,radio nets,volunteer|Free · US|Free|22222|Licensed hams who provide emergency comms for local agencies.
SKYWARN storm spotters|https://www.weather.gov/skywarn|community|weather,volunteer,training|Free · US|Free|22222|Free NWS spotter training.
Red Cross volunteering|https://www.redcross.org/volunteer/become-a-volunteer.html|community|volunteer,shelters|Free · US|Free|22222|Shelter, blood and disaster volunteering.
Medical Reserve Corps|https://aspr.hhs.gov/MRC|community|volunteer,medical|Free · US|Free|22222|Medical and non-medical volunteers who support local public health.
Team Rubicon|https://teamrubiconusa.org|community|volunteer,veterans,disaster relief|Free · US · UK · CA · AU|Free|22222|Veteran-led disaster response; civilians can join.
Mutual Aid Disaster Relief|https://mutualaiddisasterrelief.org|community|mutual aid,grassroots|Free · US|Free|11222|Grassroots mutual-aid network for disaster response.
Black Emergency Managers Association|https://www.blackemergmanagersassociation.org|community|professional,Black-led,emergency management|Free · US|Free|21222|Black-led association of emergency managers; preparedness outreach and mentoring.
National African American Gun Association|https://naaga.co|community|firearms training,Black-led|US|$|21212|Firearms education and range days for African American gun owners; local chapters.
Secure Community Network|https://www.securecommunitynetwork.org|community|security,Jewish,training|Free · US|Free|22222|Official safety and security group for the US Jewish community; threat info and training.
Community Security Service|https://thecss.org|community|security,Jewish,volunteer|Free · US|Free|21222|Trains volunteers to protect Jewish community events and buildings.
CISA: protecting houses of worship|https://www.cisa.gov/topics/physical-security/protecting-houses-worship|community|faith,security,official|Free · US|Free|22222|Free security assessments and guides for all faiths.
FEMA Nonprofit Security Grant Program|https://www.fema.gov/grants/preparedness/nonprofit-security|community|faith,nonprofits,funding|Free · US|Free|22222|Federal grants for security upgrades at nonprofits and houses of worship.
Sheepdog Church Security|https://sheepdogchurchsecurity.net|community|faith,church security,training|US|$|11212|Training and resources for volunteer church safety teams.
Pink Pistols|https://www.pinkpistols.org|community|firearms,LGBTQ|US|Free|11222|Volunteer LGBTQ firearms-safety and self-defense group with local chapters.
Operation Blazing Sword|https://www.blazingsword.org|community|firearms training,LGBTQ|US|Free|11222|Directory of volunteer instructors offering intro firearms lessons to LGBTQ people.
A Girl & A Gun|https://agirlandagun.org|community|firearms training,women|US|$|21212|Women's shooting league with local chapters and training nights.
Armed Women of America (formerly The Well Armed Woman chapters)|https://armedwomen.org|community|firearms training,women|US|$|21212|Nonprofit with about 300 local women's chapters that meet monthly for classroom and range time.
Liberal Gun Club|https://theliberalgunclub.com|community|firearms,political left|US|$|11222|Gun-owner group for liberals and progressives; education and range events.
Socialist Rifle Association|https://socialistra.org|community|firearms,political left|US|$|01222|Left-wing gun-owner group; chapters vary in activity.
National Rifle Association|https://home.nra.org|community|firearms,training,2A|US|$$|21212|Largest US gun-rights group; safety and training programs.
Second Amendment Foundation|https://saf.org|community|firearms,2A,legal|US|$|21222|Gun-rights legal advocacy group.
Gun Owners of America|https://www.gunowners.org|community|firearms,2A,lobbying|US|$|11222|Gun-rights lobbying group.
FEMA "Are You Ready?" (IS-22)|https://training.fema.gov/is/courseoverview.aspx?code=IS-22.a|books|free,official,guide|Free · Global|Free|22222|FEMA's in-depth citizen preparedness guide as a free course.
Army Publishing Directorate|https://armypubs.army.mil|books|field manuals,free|Free · Global|Free|22222|Official source for public Army field manuals (survival, first aid, land navigation).
Hesperian: Where There Is No Doctor|https://en.hesperian.org/hhg/Where_There_Is_No_Doctor_Series|books|medical,free|Free · Global|Free|22222|The classic community health manual for when no doctor is available; free online.
Internet Archive: FM 21-76 survival manual|https://archive.org/details/Fm21-76SurvivalManual|books|survival,free,field manual|Free · Global|Free|21222|Scanned copy of the Army survival field manual.
Kiwix (offline Wikipedia)|https://kiwix.org|books|offline,reference,free|Free · Global|Free|22222|Download all of Wikipedia and other references to read with no internet.
"""
# Know the landscape: research sources on militias and extremist groups (awareness only; nothing here is joinable or endorsed).
RESEARCH = [
 ("ADL: hate symbols database", "https://www.adl.org/resources/hate-symbols/search", "Advocacy group (Jewish civil rights). Widely cited; critics say some definitions are broad.", "Glossary of extremist symbols, slogans and group names."),
 ("ADL: H.E.A.T. Map", "https://www.adl.org/resources/tools-to-track-hate/heat-map", "Advocacy group. Data drawn from news and law-enforcement reports.", "Map of US extremist incidents, plots and propaganda by state."),
 ("SPLC: Hate Map", "https://www.splcenter.org/hate-map", "Advocacy group (civil rights). Widely cited; critics dispute some designations.", "Map of groups the SPLC classifies as hate or antigovernment groups, by state."),
 ("SPLC: Extremist Files", "https://www.splcenter.org/resources/extremist-files", "Advocacy group. Profiles cite public records and court cases.", "Profiles of groups and individuals, including militia movements."),
 ("GW Program on Extremism", "https://extremism.gwu.edu", "Academic (George Washington University).", "Research, court-record trackers and reports on violent extremism."),
 ("START / University of Maryland", "https://www.start.umd.edu", "Academic, DHS-funded research center; runs the Global Terrorism Database.", "Global data on terrorist attacks and radicalization research."),
 ("CSIS: Warfare, Irregular Threats & Terrorism", "https://www.csis.org/programs/warfare-irregular-threats-and-terrorism-program", "Nonpartisan think tank.", "Data-driven reports on domestic terrorism trends."),
 ("ACLED: United States", "https://acleddata.com", "Independent conflict-data nonprofit.", "Event data on political violence and demonstrations, including armed groups."),
 ("DHS: National Terrorism Advisory System", "https://www.dhs.gov/national-terrorism-advisory-system", "US government.", "Official public terrorism bulletins and advisories."),
 ("DHS: Homeland Threat Assessment", "https://www.dhs.gov/publication/homeland-threat-assessment", "US government.", "Yearly public assessment of threats, including domestic violent extremism."),
 ("FBI: terrorism", "https://www.fbi.gov/investigate/terrorism", "US government (law enforcement).", "How the FBI defines domestic terrorism; how to report threats (tips.fbi.gov)."),
]
