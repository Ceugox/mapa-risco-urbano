export type Place = { lat: number; lng: number; label: string };

const SP_BOUNDS = { north: -23.3, south: -24.05, east: -46.3, west: -47.0 };

let placesService: google.maps.places.PlacesService | null = null;

async function placesTextSearch(query: string): Promise<Place[]> {
  const lib = (await google.maps.importLibrary("places")) as google.maps.PlacesLibrary;
  placesService ??= new lib.PlacesService(document.createElement("div"));
  const found = await new Promise<google.maps.places.PlaceResult[]>((resolve) => {
    placesService?.textSearch({ query, bounds: SP_BOUNDS }, (results, code) =>
      resolve(code === google.maps.places.PlacesServiceStatus.OK && results ? results : []),
    );
  });
  return found.slice(0, 4).flatMap((result) => {
    const loc = result.geometry?.location;
    return loc
      ? [{ lat: loc.lat(), lng: loc.lng(), label: `${result.name} — ${result.formatted_address}` }]
      : [];
  });
}

async function nominatimSearch(query: string): Promise<Place[]> {
  const res = await fetch(
    `https://nominatim.openstreetmap.org/search?format=json&limit=4&countrycodes=br&q=${encodeURIComponent(query)}`,
  );
  const arr: { lat: string; lon: string; display_name: string }[] = await res.json();
  return arr.map((item) => ({
    lat: parseFloat(item.lat),
    lng: parseFloat(item.lon),
    label: item.display_name,
  }));
}

export async function searchPlaces(q: string): Promise<Place[]> {
  const query = q.toLowerCase().includes("paulo") ? q : `${q}, São Paulo`;
  try {
    const out = await placesTextSearch(query);
    if (out.length) return out;
  } catch {
    // Places indisponível na chave; cai no Nominatim.
  }
  try {
    return await nominatimSearch(query);
  } catch {
    return [];
  }
}
