from flask import Flask, render_template, request, jsonify, url_for
import requests
import os, io

app = Flask(__name__)

# Pl@ntNet API Key
PLANTNET_API_KEY = os.getenv("PLANTNET_API_KEY", "2b10EvAJaLzB73gOR3lkz2Cuwu")
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
    "Bougainvillea glabra": "Paper Flower",
    "Bougainvillea spectabilis": "Paper Flower"
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

@app.route("/about")
def about():
    return render_template("about.html")


# Fetch taxonomy and geographic distribution data from GBIF API
def get_gbif_data(scientific_name):
    gbif_data = {"taxonomy": "Not Found", "distribution": "Unknown"}
    try:
        species_search_url = f"{GBIF_API_URL}/species?name={scientific_name}"
        response = requests.get(species_search_url, timeout=10)
        species_data = response.json()

        if response.status_code == 200 and "results" in species_data and species_data["results"]:
            species_info = species_data["results"][0]
            species_id = species_info.get("key")

            gbif_data["taxonomy"] = (
                f"Kingdom: {species_info.get('kingdom', 'Unknown')}, "
                f"Phylum: {species_info.get('phylum', 'Unknown')}, "
                f"Class: {species_info.get('class', 'Unknown')}, "
                f"Order: {species_info.get('order', 'Unknown')}, "
                f"Family: {species_info.get('family', 'Unknown')}"
            )

            if species_id:
                distribution_url = f"{GBIF_API_URL}/species/{species_id}/distributions"
                dist_response = requests.get(distribution_url, timeout=10)
                dist_data = dist_response.json()

                locations = [entry.get("area", "Unknown") for entry in dist_data.get("results", []) if "area" in entry]
                if locations:
                    gbif_data["distribution"] = ", ".join(set(locations))
                else:
                    occurrence_url = f"{GBIF_API_URL}/occurrence/search?taxonKey={species_id}&limit=10"
                    occurrence_response = requests.get(occurrence_url, timeout=10)
                    occurrence_data = occurrence_response.json()

                    if "results" in occurrence_data:
                        countries = {entry.get("country") for entry in occurrence_data["results"] if "country" in entry}
                        if countries:
                            gbif_data["distribution"] = ", ".join(countries)

    except Exception as e:
        print("Error fetching GBIF data:", e)

    return gbif_data


# ✅ Render-safe identify route
@app.route("/identify", methods=["POST"])
def identify_plant():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        # ✅ Read image in memory (no disk save)
        image_bytes = io.BytesIO(file.read())
        files = {"images": ("plant.jpg", image_bytes, "image/jpeg")}
        params = {"api-key": PLANTNET_API_KEY}

        response = requests.post(PLANTNET_API_URL, files=files, params=params, timeout=25)

        print("PlantNet API status:", response.status_code)
        print("PlantNet raw response:", response.text[:500])  # ✅ Log first 500 chars for debugging

        if response.status_code != 200:
            return jsonify({"error": f"PlantNet API error: {response.status_code}"}), 500

        result = response.json()
        if "results" not in result or not result["results"]:
            return jsonify({"error": "No plant identified."}), 404

        best_plant = max(result["results"], key=lambda x: x["score"])
        scientific_name = best_plant["species"]["scientificNameWithoutAuthor"]
        probability = best_plant["score"]

        common_name = COMMON_NAMES.get(scientific_name, scientific_name)
        ayurvedic_use = AYURVEDIC_USES.get(scientific_name, "No Ayurvedic uses found.")
        gbif_info = get_gbif_data(scientific_name)

        return jsonify({
            "common_name": common_name,
            "scientific_name": scientific_name,
            "confidence": f"{probability:.2%}",
            "taxonomy": gbif_info["taxonomy"],
            "distribution": gbif_info["distribution"],
            "ayurvedic_use": ayurvedic_use
        })

    except requests.exceptions.Timeout:
        return jsonify({"error": "PlantNet API request timed out. Please try again."}), 504
    except Exception as e:
        print("Error in /identify:", e)
        return jsonify({"error": f"Server error: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)
