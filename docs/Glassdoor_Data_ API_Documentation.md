Company Search​

Search for companies (employers) on Glassdoor.

Query Parameters

query Type: string required
Search query or Company ID

limit Type: number min:  1 max:  100 default: 10
Maximum number of results to return.
domain

Type: stringenum default:"www.glassdoor.com"

The Glassdoor domain to use.
    www.glassdoor.com
    www.glassdoor.co.uk
    www.glassdoor.com.ar
    www.glassdoor.com.au
    www.glassdoor.be


REQUEST EXAMPLE
import http.client

conn = http.client.HTTPSConnection("api.openwebninja.com")

headers = { 'x-api-key': "YOUR_SECRET_TOKEN" }

conn.request("GET", "/realtime-glassdoor-data/company-search", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))

RESPONSE EXAMPLE
{
    "value": {
        "status": "OK",
        "request_id": "cb4312c6-8060-4ee8-8538-018f9d92a573",
        "parameters": {
        "query": "goo",
        "domain": "www.glassdoor.com",
        "limit": 10
        },
        "data": [
        {
            "company_id": 1145391,
            "name": "Goo.Com",
            "company_link": "https://www.glassdoor.com/Overview/Working-at-Goo-Com-EI_IE1145391.11,18.htm",
            "rating": 4.3,
            "review_count": 2,
            "salary_count": 2,
            "job_count": 0,
            "headquarters_location": "Trezzano sul Naviglio, Italy",
            "logo": "https://media.glassdoor.com/sql/1145391/goo-com-squarelogo-1458658483643.png",
            "company_size": "1 to 50 Employees",
            "company_size_category": "SMALL",
            "company_description": "Goo.com Srl is a dynamic Italian Company. We are IT Solution Provider, System Integrator and, above all, IDEAS DEVELOPER! We provide: - IT **TOP** Consultancy. - Software Engineering, Software Architecture and Hardware Engineering services. - Web and Mobile Responsive development. - Consolidate and Certified SysAdmin experience. - Software ad hoc. Our Customers and Partners: Have a look here: http://goodotcom.com/pages/chi_siamo Our Story: A long time ago in a galaxy far, far away, our first company SOPRIT was funded. Back in the 1999 we took the challenge to support our Customers in the process of integration and optimisation of their resources. We developed customised solutions for their security systems and automation. After years of experience we founded Goo.com to offer technologically advanced solutions with the highest standards of quality and reliability.",
            "industry": "Enterprise Software & Network Solutions",
            "website": "https://www.goodotcom.com",
            "company_type": "Company - Private",
            "revenue": "Unknown / Non-Applicable",
            "business_outlook_rating": 1,
            "career_opportunities_rating": 4,
            "ceo": "Marco Simone",
            "ceo_rating": 0,
            "compensation_and_benefits_rating": 5,
            "culture_and_values_rating": 5,
            "diversity_and_inclusion_rating": 0,
            "recommend_to_friend_rating": 1,
            "senior_management_rating": 4.7,
            "work_life_balance_rating": 4,
            "stock": null,
            "year_founded": null,
            "reviews_link": "https://www.glassdoor.com/Reviews/Goo-Com-Reviews-E1145391.htm",
            "jobs_link": "https://www.glassdoor.com/Jobs/Goo-Com-Jobs-E1145391.htm",
            "faq_link": "https://www.glassdoor.com/FAQ/Goo-Com-Questions-E1145391.htm",
            "competitors": [],
            "office_locations": [],
            "best_places_to_work_awards": []
        },
        {
            "company_id": 107591,
            "name": "WATG",
            "company_link": "https://www.glassdoor.com/Overview/Working-at-WATG-EI_IE107591.11,15.htm",
            "rating": 3.5,
            "review_count": 186,
            "salary_count": 351,
            "job_count": 0,
            "headquarters_location": "Irvine, CA",
            "logo": "https://media.glassdoor.com/sql/107591/watg-squarelogo-1543326423910.png",
            "company_size": "201 to 500 Employees",
            "company_size_category": "MEDIUM",
            "company_description": "From our dawning days in 1945 Honolulu, we have pioneered hospitality, tourism and destination design. Independent to this day, we are a global multi-disciplinary design firm specializing in Strategy, Master Planning, Architecture, Landscape and Wimberly Interiors. We are a team of 500 creative, world-traveling professionals designing landmark urban and leisure destinations with eight offices across three continents.",
            "industry": "Architectural & Engineering Services",
            "website": "https://www.watg.com",
            "company_type": "Company - Private",
            "revenue": "$25 to $100 million (USD)",
            "business_outlook_rating": 0.67,
            "career_opportunities_rating": 3.1,
            "ceo": "David D Moore ",
            "ceo_rating": 0.69,
            "compensation_and_benefits_rating": 3.6,
            "culture_and_values_rating": 3.4,
            "diversity_and_inclusion_rating": 3.6,
            "recommend_to_friend_rating": 0.66,
            "senior_management_rating": 3.1,
            "work_life_balance_rating": 3.5,
            "stock": null,
            "year_founded": 1945,
            "reviews_link": "https://www.glassdoor.com/Reviews/WATG-Reviews-E107591.htm",
            "jobs_link": "https://www.glassdoor.com/Jobs/WATG-Jobs-E107591.htm",
            "faq_link": "https://www.glassdoor.com/FAQ/WATG-Questions-E107591.htm",
            "competitors": [
            {
                "id": 267586,
                "name": "HBA Architecture & Interior Design"
            },
            {
                "id": 376657,
                "name": "Rockwell Group"
            },
            {
                "id": 1381077,
                "name": "Populous"
            }
            ],
            "office_locations": [
            {
                "city": "New York, NY",
                "country": "United States"
            },
            {
                "city": "Honolulu, HI",
                "country": "United States"
            },
            {
                "city": "Irvine, CA",
                "country": "United States"
            },
            {
                "city": "Los Angeles, CA",
                "country": "United States"
            },
            {
                "city": "Shanghai, Shanghai",
                "country": "China"
            },
            {
                "city": "London, England",
                "country": "United Kingdom"
            },
            {
                "city": "Singapore",
                "country": "Singapore"
            }
            ],
            "best_places_to_work_awards": []
        }
        ]
    }
}


RESPONSE SCHEMA

{
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "description": "The status of the API response",
      "examples": [
        "success"
      ]
    },
    "request_id": {
      "type": "string",
      "description": "A unique identifier for the request",
      "examples": [
        "3a6c2d20-2e45-4f4c-9b3c-8ef7be1c0a94"
      ]
    },
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "The search query string",
          "examples": [
            "apple"
          ]
        },
        "limit": {
          "type": "integer",
          "description": "The maximum number of results to return",
          "examples": [
            10
          ]
        }
      }
    },
    "data": {
      "type": "array",
      "items": {
        "type": "object"
      }
    }
  }
}