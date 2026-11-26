// Utilidades de mapa sobre as malhas TopoJSON do IBGE.

/** Primeiro (e único) objeto de um TopoJSON do IBGE: BRGR, BRUF, BRIN, BRIM... */
export const objetoDe = (topo) => topo.objects[Object.keys(topo.objects)[0]];

/**
 * Feições com o sentido dos anéis que o d3 espera (anel externo no sentido horário).
 * O padrão GeoJSON é o contrário; sem isso o d3 entende cada polígono como "o mundo menos o polígono".
 */
export function feicoes(topo) {
  const d3 = window.d3;
  const colecao = window.topojson.feature(topo, objetoDe(topo));
  for (const f of colecao.features) {
    if (d3.geoArea(f) > 2 * Math.PI) {
      const poligonos = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
      for (const p of poligonos) for (const anel of p) anel.reverse();
    }
  }
  return colecao;
}
