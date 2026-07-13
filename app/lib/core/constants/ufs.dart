/// Lista canônica de UFs (espelha frontend/src/components/Header.jsx).
class Ufs {
  static const List<String> all = [
    'sp', 'rj', 'mg', 'rs', 'ba', 'pr', 'pe', 'ce', 'pa', 'sc', 'br',
  ];

  static const Map<String, String> labels = {
    'sp': 'São Paulo',
    'rj': 'Rio de Janeiro',
    'mg': 'Minas Gerais',
    'rs': 'Rio Grande do Sul',
    'ba': 'Bahia',
    'pr': 'Paraná',
    'pe': 'Pernambuco',
    'ce': 'Ceará',
    'pa': 'Pará',
    'sc': 'Santa Catarina',
    'br': 'Brasil',
  };

  static String label(String uf) => labels[uf] ?? uf.toUpperCase();
}
