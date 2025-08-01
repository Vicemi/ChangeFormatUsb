import json
import os
import sys

def resource_path(relative_path):
    """Obtiene la ruta absoluta al recurso"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class Translator:
    def __init__(self, lang="es"):
        self.language = lang
        self.translations = self.load_translations(lang)
    
    def load_translations(self, lang_code):
        """Carga traducciones desde archivo JSON"""
        try:
            file_path = resource_path(f"resources/translations/{lang_code}.json")
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            # Fallback a traducciones integradas
            return self.get_fallback_translations()
    
    def get_fallback_translations(self):
        """Traducciones de fallback"""
        return {
            # ... (contenido idéntico a tus traducciones actuales)
        }
    
    def set_language(self, lang_code):
        """Cambia el idioma cargando el archivo correspondiente"""
        self.language = lang_code
        self.translations = self.load_translations(lang_code)
    
    def gettext(self, key):
        return self.translations.get(key, key)
    
    def get_available_languages(self):
        return {
            "es": "Español",
            "en": "English"
        }