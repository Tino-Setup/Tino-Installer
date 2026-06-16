import json
import os
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
from i18n import get_base_path

class AdditionalTask(BaseModel):
    """Model representing an additional task to execute during installation."""
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(alias="Name")
    command: str = Field(alias="Command")

class LocalizationData(BaseModel):
    """Model representing localized strings and configuration for a specific language."""
    model_config = ConfigDict(populate_by_name=True)
    
    language_label: str = Field(alias="Language Label")
    application_name: str = Field(alias="Application Name")
    application_description: str = Field(alias="Application Description")
    application_pre_install_information: Optional[str] = Field(None, alias="Application Pre Install Information")
    application_license: Optional[str] = Field(None, alias="Application License")
    application_post_install_information: Optional[str] = Field(None, alias="Application Post Install Information")
    application_additional_tasks: List[AdditionalTask] = Field(default_factory=list, alias="Application Additional Tasks")

class TinoConfig(BaseModel):
    """Main configuration model for the Tino Installer, loaded from installer.tino."""
    model_config = ConfigDict(populate_by_name=True)

    application_version: str = Field(alias="Application Version")
    application_author: str = Field(alias="Application Author")
    application_website: Optional[str] = Field(None, alias="Application Website")
    application_icon: str = Field(alias="Application Icon")

    application_installation_path: str = Field(alias="Application Installation Path")
    application_executable_path: str = Field(alias="Application Executable Path")
    application_executable_source: str = Field(alias="Application Executable Source")
    application_icon_path: str = Field("", alias="Application Icon Path")
    application_icon_source: str = Field("", alias="Application Icon Source")
    application_desktop_path: str = Field("", alias="Application Desktop Path")
    application_desktop_source: str = Field("", alias="Application Desktop Source")
    application_compression_type: str = Field(alias="Application Compression Type")
    application_name_slug: str = Field("", alias="Application Name Slug")
    application_uninstaller_icon_path: str = Field("", alias="Application Uninstaller Icon Path")
    application_pre_installation_script: Optional[str] = Field(None, alias="Application Pre Installation Script")
    application_post_installation_script: Optional[str] = Field(None, alias="Application Post Installation Script")

    localization: Dict[str, LocalizationData] = Field(alias="Localization")

    current_lang: str = "en_US"
    @property
    def local(self) -> LocalizationData:
        """Returns the localization data for the current language, with fallback to the first available."""
        if self.current_lang in self.localization:
            return self.localization[self.current_lang]
        return self.localization.get("en_US", next(iter(self.localization.values())))

    application_pre_install_information_text: str = ""
    application_license_text: str = ""
    application_post_install_information_text: str = ""

def load_data() -> TinoConfig:
    """Loads the installer.tino file."""
    config_file = os.path.join(get_base_path(), "installer.tino")
    if not os.path.exists(config_file):
        raise RuntimeError(f"Configuration file '{config_file}' not found.")
    try:
        with open(config_file, encoding='utf-8') as f:
            data_dict = json.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load {config_file}: {e}") from e

    config = TinoConfig(**data_dict)

    return config

def refresh_texts(config: TinoConfig):
    """Loads external text files based on the current language."""
    text_mapping = {
        "application_license": "application_license_text",
        "application_pre_install_information": "application_pre_install_information_text",
        "application_post_install_information": "application_post_install_information_text"
    }

    for path_attr, text_attr in text_mapping.items():
        path = getattr(config.local, path_attr, None)
        if path:
            if not os.path.isabs(path):
                path = os.path.join(get_base_path(), path)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    setattr(config, text_attr, f.read())
            except Exception:
                setattr(config, text_attr, "")