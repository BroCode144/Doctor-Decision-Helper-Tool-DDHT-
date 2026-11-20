"""Indian cities the booking page offers, with approximate centre coordinates (public knowledge, typed in by hand; no
API or download). The patient's phone uses the coordinates to find the nearest city ITSELF, so the patient's exact
location never leaves the phone: only the chosen city name is sent and stored.

Names must match the city names used in Admin > Local diseases and on hospitals (matching ignores case).
Satellite towns (Thane, Navi Mumbai, Gurugram, Noida, ...) are left out on purpose: the nearest-city search maps
them to their big city, which is where disease patterns are reported.
"""

CITIES: list[tuple[str, str, float, float]] = [  # name, state, latitude, longitude
    ("Agartala", "Tripura", 23.8315, 91.2868), ("Agra", "Uttar Pradesh", 27.1767, 78.0081),
    ("Ahmedabad", "Gujarat", 23.0225, 72.5714), ("Amritsar", "Punjab", 31.6340, 74.8723),
    ("Aurangabad", "Maharashtra", 19.8762, 75.3433), ("Bengaluru", "Karnataka", 12.9716, 77.5946),
    ("Bhopal", "Madhya Pradesh", 23.2599, 77.4126), ("Bhubaneswar", "Odisha", 20.2961, 85.8245),
    ("Chandigarh", "Chandigarh", 30.7333, 76.7794), ("Chennai", "Tamil Nadu", 13.0827, 80.2707),
    ("Coimbatore", "Tamil Nadu", 11.0168, 76.9558), ("Dehradun", "Uttarakhand", 30.3165, 78.0322),
    ("Delhi", "Delhi", 28.6139, 77.2090), ("Guwahati", "Assam", 26.1445, 91.7362),
    ("Gwalior", "Madhya Pradesh", 26.2183, 78.1828), ("Hyderabad", "Telangana", 17.3850, 78.4867),
    ("Imphal", "Manipur", 24.8170, 93.9368), ("Indore", "Madhya Pradesh", 22.7196, 75.8577),
    ("Jabalpur", "Madhya Pradesh", 23.1815, 79.9864), ("Jaipur", "Rajasthan", 26.9124, 75.7873),
    ("Jammu", "Jammu and Kashmir", 32.7266, 74.8570), ("Jodhpur", "Rajasthan", 26.2389, 73.0243),
    ("Kanpur", "Uttar Pradesh", 26.4499, 80.3319), ("Kochi", "Kerala", 9.9312, 76.2673),
    ("Kolhapur", "Maharashtra", 16.7050, 74.2433), ("Kolkata", "West Bengal", 22.5726, 88.3639),
    ("Kozhikode", "Kerala", 11.2588, 75.7804), ("Lucknow", "Uttar Pradesh", 26.8467, 80.9462),
    ("Ludhiana", "Punjab", 30.9010, 75.8573), ("Madurai", "Tamil Nadu", 9.9252, 78.1198),
    ("Mangaluru", "Karnataka", 12.9141, 74.8560), ("Meerut", "Uttar Pradesh", 28.9845, 77.7064),
    ("Mumbai", "Maharashtra", 19.0760, 72.8777), ("Mysuru", "Karnataka", 12.2958, 76.6394),
    ("Nagpur", "Maharashtra", 21.1458, 79.0882), ("Nashik", "Maharashtra", 19.9975, 73.7898),
    ("Panaji", "Goa", 15.4909, 73.8278), ("Patna", "Bihar", 25.5941, 85.1376),
    ("Prayagraj", "Uttar Pradesh", 25.4358, 81.8463), ("Puducherry", "Puducherry", 11.9416, 79.8083),
    ("Pune", "Maharashtra", 18.5204, 73.8567), ("Raipur", "Chhattisgarh", 21.2514, 81.6296),
    ("Rajkot", "Gujarat", 22.3039, 70.8022), ("Ranchi", "Jharkhand", 23.3441, 85.3096),
    ("Shillong", "Meghalaya", 25.5788, 91.8933), ("Shimla", "Himachal Pradesh", 31.1048, 77.1734),
    ("Srinagar", "Jammu and Kashmir", 34.0837, 74.7973), ("Surat", "Gujarat", 21.1702, 72.8311),
    ("Thiruvananthapuram", "Kerala", 8.5241, 76.9366), ("Tiruchirappalli", "Tamil Nadu", 10.7905, 78.7047),
    ("Vadodara", "Gujarat", 22.3072, 73.1812), ("Varanasi", "Uttar Pradesh", 25.3176, 82.9739),
    ("Vijayawada", "Andhra Pradesh", 16.5062, 80.6480), ("Visakhapatnam", "Andhra Pradesh", 17.6868, 83.2185),
    ("Warangal", "Telangana", 17.9689, 79.5941),
]
OTHER = "other"
NEAREST_MAX_KM = 75  # the phone only fills in a city within this distance; otherwise the patient picks


def options() -> list[dict]:
    """Choices for the city questions, with coordinates for the phone's nearest-city search."""
    return [{"value": n, "label": f"{n} ({s})", "lat": lat, "lon": lon} for n, s, lat, lon in CITIES] + [
        {"value": OTHER, "label": "Other / not in the list"}]
