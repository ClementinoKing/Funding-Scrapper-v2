import asyncio
from .ai_enhancement import AIEnhancer

def test():
    config = {
        "aiProvider": "openai",
        "aiModel": "gpt-4o-mini",
        "openaiKey": "your-openai-api-key",
    }

    enhancer = AIEnhancer(config)

    item = {"url": "https://nydawebsite.azurewebsites.net/Products-Services/NYDA-Grant-Programme.html", "title": "NYDA Grant Programme"}
    page_text = "Some scraped content..."

    result = asyncio.run(enhancer.enhance(item, page_text))

    print(result)


if __name__ == "__main__":
    test()




def content() -> None:
    return """
What is NYDA Grant Programme?
The NYDA Grant Programme is designed to provide young entrepreneurs with an opportunity to access both financial and non- financial business development support in order to enable them to establish or grow their businesses.

The programme focuses on youth entrepreneurs who are at promising and new stages of enterprise development. Young people whose business ideas qualify for the Grant Programme, depending on their individual needs, will also undergo some of the NYDA’s non- financial support services, including:

• Mentorship

• Business Consultancy Services

• Market Linkages

• Business Management Training Programme

• Youth Co-operative Development Programme

The NYDA Grant Funding program excludes the following forms of funding requests:

• Partial funding, co-funding or funding towards a deposit for a loan from another lending establishment;

• Where an application is made by current NYDA staff members, Board Committee Members or Member of the Accounting Authority;

• Pyramid Sales Schemes.

• Fall within the gambling, gaming with a chance at making money, pyramid sales scheme, loan shark or sex industries (prostitution), and/or operates illegal activities.

• Businesses or shareholders of businesses that are still owing the NYDA through loan funding.

• Businesses or shareholders of businesses that received NYDA SME loan funding.

• Businesses or shareholders of businesses that had their loans written off by NYDA.

• Businesses that have an annual turnover exceeding R750,000.00 except for cooperatives whose annual  turnover must not exceed R1000,000.00

• Second hand equipment, except for industrial equipment with a minimum balance lifespan of five years;

• Tobacco as a primary income generator;

• Alcohol as a primary income generator;

• Are investment trusts or venture capital / private equity funds;

• Require finance to substitute an existing financier;

• An individual or business shall not receive a cumulative grant amount above R200 000 from NYDA during their lifetime except for cooperatives (for agriculture and technology related projects the maximum cumulative value is R250,000.00).

• A member of a business or cooperative enterprise who resigns from the business or cooperative can only apply for grant funding after two years from the date of resignation from the business that has been funded by the NYDA in the past from the grant programme.

• Require funding for prototyping except for cell phone application development.

• Require seed capital for research and development;

• Require funding for patent registration.

• Require funding to purchase exclusive business/distribution rights

• Shareholders/members are natural persons who lack contractual capacity by virtue of:

-- being of unsound mind;

-- Have a record of fraud and/or corruption except for youth in conflict with the law who have been rehabilitated;

-- Where the owner/applicant is an un-rehabilitated insolvent;

-- Where the owner/applicant is attending high school other than tertiary institutions;

• NYDA shall not provide grant funding for vehicles

• The grant recipient shall not use NYDA funds to do the following:

• To pay a bribe;

• Re-finance any existing loans;

• Any material purpose not contained in the application for grant or defined during due diligence stage and detailed in the approved Terms & Conditions, unless where written approval has been granted by NYDA;

• To settle overdue or outstanding South African Revenue Service liabilities, whether current on non-current.

• NYDA will not provide grant funding to a client that has benefited from another Development Finance Institution to an amount above R500,000.00.

• NYDA will not provide a grant to an applicant who has  been convicted of fraud.

Utilisation of the Grant Funding

The grant can be utilised for the following:

• To purchase movable and immovable assets.

• Bridging finance.

• Shop renovations.

• Working capital paid directly to the grantee.

• Co-funding with legal entities only.

Grant types

Grants will be granted to the following:

• Individuals

• Co-operatives

•  Community Development Facilitation Projects

Service Delivery Standards

• The grant applications will be processed at a branch within 30 working days

• Disbursement for approved will be processed at the Head Office within 30 working days

Credit Checks

• The NYDA shall conduct credit checks for all grant applications for funding.

• A grant applicant who is under debt administration shall not be considered for funding.

Branch Grant Approval and Review Committee (BGARC) Decision

• The decision of BGARC are final and binding on the applicant

•  The applicant cannot appeal the decision of the BGARC, however they can re-apply for grant funding


Application Process
Those who are eligible to apply:

    Are youth from 18-35 years of age
    Are youth with skills, experience or; with the potential skill, appropriate for the enterprise that they conduct or intend to conduct.
    Are South African citizens
    Are South African residents

Application Process/Procedure

    You must apply 3 months before you turn 35 years,
    Submission of all required documentation,
    Proof of attending Business Management Training  course,
    Business Pitch presentation of 10 minutes - in person or telephonically,
    Due Diligence assessment conducted by the NYDA official on the business.

How to access the NYDA Grant Programme

    Click here to register on the NYDA Portal(https://erp.nyda.gov.za/register)
    Contact our Call Centre on 0800 58 58 58
    Or visit your nearest NYDA Branch(https://nydawebsite.azurewebsites.net/Contact-Us.html)
"""