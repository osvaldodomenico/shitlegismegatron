/// Cargos canônicos (espelha frontend/src/components/Header.jsx).
class Cargos {
  static const List<String> all = [
    'presidente',
    'governador',
    'senador',
    'dep_federal',
    'dep_estadual',
  ];

  static const Map<String, String> labels = {
    'presidente': 'Presidente',
    'governador': 'Governador',
    'senador': 'Senador',
    'dep_federal': 'Deputado Federal',
    'dep_estadual': 'Deputado Estadual',
  };

  static String label(String cargo) => labels[cargo] ?? cargo;
}
