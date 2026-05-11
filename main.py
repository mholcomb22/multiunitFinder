from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI(title="Boise Multi-Unit Finder")

# Mock data: Multi-unit properties in Boise, ID under $1M
class Property(BaseModel):
    id: int
    address: str
    price: int
    units: int
    beds: int
    baths: float
    sqft: int
    description: str
    image: str  # placeholder URL

properties_db: List[Property] = [
    {
        "id": 1,
        "address": "1234 Maple Ave, Boise, ID 83702",
        "price": 675000,
        "units": 2,
        "beds": 4,
        "baths": 3.0,
        "sqft": 2800,
        "description": "Charming duplex with separate yards and updated kitchens.",
        "image": "https://picsum.photos/id/1015/600/400"
    },
    {
        "id": 2,
        "address": "567 Pine St, Boise, ID 83704",
        "price": 899000,
        "units": 3,
        "beds": 6,
        "baths": 4.5,
        "sqft": 4200,
        "description": "Triplex near downtown with strong rental income potential.",
        "image": "https://picsum.photos/id/133/600/400"
    },
    {
        "id": 3,
        "address": "890 Elm Dr, Boise, ID 83705",
        "price": 450000,
        "units": 2,
        "beds": 3,
        "baths": 2.0,
        "sqft": 2100,
        "description": "Affordable duplex in quiet neighborhood. Great for owner-occupy + rent.",
        "image": "https://picsum.photos/id/201/600/400"
    },
    {
        "id": 4,
        "address": "2345 Birch Ln, Boise, ID 83706",
        "price": 950000,
        "units": 4,
        "beds": 8,
        "baths": 6.0,
        "sqft": 5100,
        "description": "4-plex investment property with excellent cash flow.",
        "image": "https://picsum.photos/id/251/600/400"
    },
    {
        "id": 5,
        "address": "1122 Cedar Ave, Boise, ID 83709",
        "price": 725000,
        "units": 2,
        "beds": 5,
        "baths": 3.5,
        "sqft": 3200,
        "description": "Modern duplex built in 2022. Energy efficient and move-in ready.",
        "image": "https://picsum.photos/id/301/600/400"
    },
]

@app.get("/", response_class=HTMLResponse)
async def home():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Boise Multi-Unit Finder</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    </head>
    <body class="bg-gray-50">
        <div class="max-w-7xl mx-auto p-6">
            <h1 class="text-4xl font-bold text-center mb-2">🏠 Boise Multi-Unit Properties</h1>
            <p class="text-center text-gray-600 mb-8">Under $1,000,000 • Live in one unit • Rent the rest</p>
            
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" id="properties">
                <!-- Populated by JavaScript -->
            </div>
        </div>

        <script>
            const properties = """ + str(properties_db).replace("'", '"') + """;

            function renderProperties(props) {
                const container = document.getElementById('properties');
                container.innerHTML = props.map(p => `
                    <div class="bg-white rounded-2xl shadow-lg overflow-hidden hover:shadow-xl transition">
                        <img src="${p.image}" class="w-full h-48 object-cover">
                        <div class="p-6">
                            <div class="flex justify-between items-start">
                                <div>
                                    <h3 class="text-2xl font-semibold">$${p.price.toLocaleString()}</h3>
                                    <p class="text-gray-500 text-sm">${p.address}</p>
                                </div>
                                <span class="px-4 py-2 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-full">${p.units}-unit</span>
                            </div>
                            <div class="mt-4 grid grid-cols-3 gap-4 text-sm">
                                <div><i class="fa-solid fa-bed mr-1"></i> ${p.beds} beds</div>
                                <div><i class="fa-solid fa-bath mr-1"></i> ${p.baths} baths</div>
                                <div><i class="fa-solid fa-ruler-combined mr-1"></i> ${p.sqft} sqft</div>
                            </div>
                            <p class="mt-4 text-gray-600 text-sm">${p.description}</p>
                            <button onclick="alert('Contact info would go here for property #' + ${p.id})" 
                                    class="mt-6 w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-xl font-medium">
                                View Details / Contact
                            </button>
                        </div>
                    </div>
                `).join('');
            }
            renderProperties(properties);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# REST API endpoint (for future integration)
@app.get("/api/properties")
async def get_properties():
    return properties_db

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)



