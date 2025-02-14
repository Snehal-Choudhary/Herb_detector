from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

# Pl@ntNet API Key
PLANTNET_API_KEY = "2b10EvAJaLzB73gOR3lkz2Cuwu"
PLANTNET_API_URL = "https://my-api.plantnet.org/v2/identify/all"
GBIF_API_URL = "https://api.gbif.org/v1"

# Common Names and Ayurvedic Uses
COMMON_NAMES = {
    "Aloe vera": "Aloe",
    "Ficus benjamina": "Weeping Fig",
    "Ocimum basilicum": "Tulsi",
    "Mangifera indica": "Mango Tree",
    "Rosa indica": "Indian Rose",
    "Azadirachta indica": "Neem",
    "Ocimum tenuiflorum": "Tulsi",
    "Bougainvillea": "Paper Flower",
    "Dalbergia sissoo": "Sheesam",
    "Hibiscus rosa-sinensis": "Hibiscus",
    "Bougainvillea glabra":"Paper Flower",
    "Bougainvillea spectabilis":"Paper Flower"
}

AYURVEDIC_USES = {
    "Aloe vera": "Used for skin healing, digestion, and cooling body heat.",
    "Ficus benjamina": "Used for treating infections and as an anti-inflammatory.",
    "Ocimum basilicum": "Commonly used for digestion, respiratory health, and immunity boosting.",
    "Mangifera indica": "Used for improving digestion and as an antioxidant.",
    "Rosa indica": "Known for cooling effects, improving skin health, and boosting immunity.",
    "Azadirachta indica": "Neem treats acne and has anti-inflammatory properties.",
    "Ocimum tenuiflorum": "Commonly used for digestion, respiratory health, and immunity boosting.",
    "Bougainvillea": "Used for treating coughs, respiratory issues, and skin infections.",
    "Dalbergia sissoo": "Used for obesity, vitiligo, fever, wounds, and intestinal parasites.",
    "Hibiscus rosa-sinensis": "Promotes healthy hair, supports skin, and removes excess body heat.",                     
    "Bougainvillea glabra": "Used for treating coughs, respiratory issues, and skin infections.",
    "Bougainvillea spectabilis": "Used for treating coughs, respiratory issues, and skin infections.",


}

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/")
def home():
    return render_template("index.html")

# Function to fetch taxonomy and geographic distribution data from GBIF API
import requests

GBIF_API_URL = "https://api.gbif.org/v1"

def get_gbif_data(scientific_name):
    gbif_data = {"taxonomy": "Not Found", "distribution": "Unknown"}

    try:
        # 1. Fetch the species ID from GBIF
        species_search_url = f"{GBIF_API_URL}/species?name={scientific_name}"
        response = requests.get(species_search_url)
        species_data = response.json()

        if response.status_code == 200 and "results" in species_data and species_data["results"]:
            species_info = species_data["results"][0]
            species_id = species_info.get("key")

            # Extract detailed taxonomy
            gbif_data["taxonomy"] = (
                f"Kingdom: {species_info.get('kingdom', 'Unknown')}, "
                f"Phylum: {species_info.get('phylum', 'Unknown')}, "
                f"Class: {species_info.get('class', 'Unknown')}, "
                f"Order: {species_info.get('order', 'Unknown')}, "
                f"Family: {species_info.get('family', 'Unknown')}"
            )

            if species_id:
                # 2. Try to fetch distribution data from the distributions API
                distribution_url = f"{GBIF_API_URL}/species/{species_id}/distributions"
                dist_response = requests.get(distribution_url)
                dist_data = dist_response.json()

                locations = [
                    entry.get("area", "Unknown") for entry in dist_data.get("results", []) if "area" in entry
                ]
                
                if locations:
                    gbif_data["distribution"] = ", ".join(set(locations))  # Remove duplicates

                else:
                    # 3. If no distribution data, use occurrence records as a backup
                    occurrence_url = f"{GBIF_API_URL}/occurrence/search?taxonKey={species_id}&limit=10"
                    occurrence_response = requests.get(occurrence_url)
                    occurrence_data = occurrence_response.json()

                    if "results" in occurrence_data:
                        countries = {entry.get("country") for entry in occurrence_data["results"] if "country" in entry}
                        if countries:
                            gbif_data["distribution"] = ", ".join(countries)

    except Exception as e:
        print("Error fetching GBIF data:", e)

    return gbif_data


@app.route("/identify", methods=["POST"])
def identify_plant():
    if "file" not in request.files:
        return jsonify({"error": "No file part"})

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"})

    if file:
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(image_path)

        params = {"api-key": PLANTNET_API_KEY}
        with open(image_path, "rb") as image_file:
            files = {"images": image_file}
            response = requests.post(PLANTNET_API_URL, files=files, params=params)

        if response.status_code == 200:
            result = response.json()
            if "results" in result and result["results"]:
                best_plant = max(result["results"], key=lambda x: x["score"])
                scientific_name = best_plant["species"]["scientificNameWithoutAuthor"]
                probability = best_plant["score"]
                
                # Get original common name from dictionary
                common_name = COMMON_NAMES.get(scientific_name, scientific_name)
                ayurvedic_use = AYURVEDIC_USES.get(scientific_name, "No Ayurvedic uses found.")

                # Fetch additional data from GBIF
                gbif_info = get_gbif_data(scientific_name)

                return jsonify({
                    "common_name": common_name,
                    "scientific_name": scientific_name,
                    "confidence": f"{probability:.2%}",
                    "taxonomy": gbif_info["taxonomy"],
                    "distribution": gbif_info["distribution"],
                    "ayurvedic_use": ayurvedic_use,
                    "image_url": image_path
                })
            else:
                return jsonify({"error": "No plant identified."})
        else:
            return jsonify({"error": f"API error: {response.status_code}"})

    return jsonify({"error": "Something went wrong"})

if __name__ == "__main__":
    app.run(debug=True)
