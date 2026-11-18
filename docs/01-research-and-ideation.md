# Research and Ideation: Centralized Drug Monitoring Unit

**Status:** Final (ideation phase) · **Date:** 6 November 2026 · **Country:** Kenya

## 1. The original idea

A centralized, secure system that brings together patient medication records from pharmacies and hospitals across the country. Any licensed pharmacist or doctor can enter a patient's ID and immediately see their dispensing history: what drug was given, when and where. The system flags duplicate or early refills to reduce drug abuse, prevent overdose, and improve patient safety and regulatory oversight.

## 2. What this kind of system is called

Internationally this is a **Prescription Drug Monitoring Program (PDMP)**, also called **Real-Time Prescription Monitoring (RTPM)**. The US and Australia have proven the model. We found no patient-level PDMP operating in East Africa. That gap is our opportunity.

## 3. Competitors and comparable systems

| System | What it does well | Where it falls short (our opening) |
|---|---|---|
| **US PDMPs: Bamboo Health PMP AWARxE + NarxCare** (40+ states) | Real-time data. Built into EHR and pharmacy software through "PMP Gateway," so clinicians don't need a separate login. Patient risk scores, charts of usage patterns, and messaging between a patient's clinicians. | Each state runs its own database, so patients cross state lines to avoid detection. NarxCare's risk scores are opaque and have been criticised for denying pain patients care. The vendor says the scores should not be the only basis for a decision. Clinicians stop checking unless use is mandatory and built into their workflow. |
| **Australia: SafeScript (Victoria, NSW) and other RTPM systems** | Records are captured **automatically** from prescribing and dispensing software in real time, so clinicians enter no extra data. Covers only a defined list of high-risk medicines. Sends alerts but **never blocks** a prescription. Mandatory in Victoria, Queensland and South Australia. | Rolled out state by state over several years. Uptake is weaker where use is voluntary (NSW). |
| **South Africa: SAHPRA Codeine Care Initiative** (planned) | Would warn pharmacists when a patient's codeine purchases exceed their allowance, and track supply from manufacturer to wholesaler. | The earlier voluntary pharmacy version failed because most pharmacies did not take part. It also faces POPI Act privacy problems and poor rural internet. We will face the same risks. |
| **Kenya: PPB track-and-trace and the National Drug Control System** | Tracks **products** (fakes, imports, import and export permits for controlled substances). Imported medicines need unique identifiers from 1 January 2027. | Tracks the box, not the patient. It cannot show that one person collected tramadol from three pharmacies in a week. |
| **Kenya: Digital Health Agency** (Client Registry, Shared Health Record on FHIR, national health data exchange, under the Digital Health Act 2023) | National patient IDs, and a legal requirement for certified systems to connect to the national exchange. | General health-data infrastructure with no features for detecting abuse. It is both our **biggest risk** (the government could add these features itself) and our **best route to market**. |

## 4. Recommendations that shaped the product

1. **Monitor only high-risk medicines, not all medication records.** Start with opioids, tramadol, codeine, benzodiazepines and other psychotropics. A narrow scope means a smaller privacy burden, less resistance from pharmacies, and stronger legal grounds.
2. **Build on the national system rather than competing with it.** Use the DHA Client Registry ID as the patient identifier and exchange data over the national exchange. Position the product as "the controlled-substance intelligence layer on Kenya's shared health record."
3. **Capture data automatically.** Connect to pharmacy point-of-sale software and hospital EMRs. Offer a very light app for small chemists, and later an SMS/USSD fallback with offline sync.
4. **Flag more than duplicate or early refills:** doctor and pharmacy shopping, dangerous combinations, total dose limits, unusual prescribers and pharmacies, and **comparing supply with dispensing** (stock received from PPB track-and-trace against stock dispensed). That comparison is our strongest differentiator.
5. **Keep alerts transparent and advisory, not black-box scores.** Every alert explains why it fired. The clinician decides. Patients can appeal.
6. **Present it as patient safety, not policing.** When an alert fires, offer a referral to counselling, NACADA services or medication-assisted treatment clinics.
7. **Give patients visibility to build trust.** As in Estonia, patients can see who accessed their record. Every access is logged and audited, in line with the Data Protection Act 2019.
8. **Plan for mandatory use from day one.** Every voluntary scheme we found had weak uptake. Adoption should come through PPB licence conditions or SHA claim rules.
9. **Treat patient identity as the hardest problem.** Duplicate or fake IDs, minors, refugees and foreigners all need handling. Match records against the Client Registry, and later add biometric checks.
10. **Build the regulator dashboard as a product in its own right.** Government pays for the insight. Clinicians use the lookup for free.

## 5. Positioning statement

> A real-time controlled-substance monitoring layer on Kenya's national health data exchange. It automatically captures every dispense of high-risk medicines, gives clinicians explainable alerts at the point of care, and gives regulators insight into diversion by reconciling supply against dispensing.

## 6. Decisions confirmed

| Question | Decision |
|---|---|
| Target country | Kenya |
| First buyer or champion | Government / Digital Health Agency |
| Project nature | Academic hackathon project now; commercial product as the end goal |
| Pilot scope | One county, general high-risk drug list (specific drugs added later) |
| MVP platform | Web app, on an architecture that can later support mobile, USSD and system integrations |

## Sources

- [Bamboo Health PMP AWARxE](https://bamboohealth.com/solutions/pmp-awarxe/) · [NarxCare](https://bamboohealth.com/solutions/narxcare/) · [Texas PMP NarxCare](https://www.pharmacy.texas.gov/PMP/Narxcare.asp) · [New Hampshire PDMP](https://Www.Dhhs.Nh.Gov/programs-services/population-health/prescription-drug-monitoring-program)
- [SafeScript Victoria](https://health.vic.gov.au/safescript/safescript-for-prescribers-and-pharmacists) · [What is SafeScript NSW](https://www.health.nsw.gov.au:443/pharmaceutical/safescript/practitioners/Pages/what-is-safescript-nsw.aspx) · [ADF: real-time monitoring](https://adf.org.au/reducing-risk/pharmaceuticals/real-time-monitoring/) · [RACGP: SafeScript turns four](https://www1.racgp.org.au/newsgp/clinical/safescript-turns-four-what-have-we-learnt)
- [Daily Maverick: SA codeine guidelines](https://www.dailymaverick.co.za/article/2024-05-02-codeine-misuse-south-africa-set-to-get-new-guidelines) · [Nigeria codeine measures](https://www.healthnews.ng/nigeria-announces-major-steps-to-address-codeine-abuse/amp/)
- [Kenya PPB traceability pilot](https://healthbusiness.co.ke/9174/kenya-pilots-pharmaceutical-traceability-platform-to-fight-illicit-drugs) · [Kenya online controlled-substance permits](https://healthbusiness.co.ke/3871/kenya-becomes-first-country-in-africa-to-minitor-import-and-export-of-controlled-substances-online) · [Imported medicines identifier requirement](https://www.kenyans.co.ke/news/126289-imported-medicines-face-new-identification-requirement-january-moh-confirms) · [The Standard: medicine tracking system](https://thestandard.ke/business/amp/health-science/article/2001555531/kenya-tightens-war-on-fake-drugs-with-a-medicine-tracking-system)
- [Digital Health Act 2023](https://new.kenyalaw.org/akn/ke/act/2023/15/eng@2023-11-24) · [Kenya Client Registry](https://cr.dha.go.ke/) · [Kenya ePrescription FHIR Implementation Guide](https://build.fhir.org/ig/IntelliSOFT-Consulting/Kenya-ePrescription-IG/background.html) · [DHA interoperability push](https://capitalfm.africa/digital-health-agency-pushes-interoperability-across-kenya/) · [SHA biometrics](https://www.standardmedia.co.ke/health/health-science/article/2001526028/duale-biometrics-to-replace-otp-use-in-sweeping-sha-reforms)
