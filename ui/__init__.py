"""User interface widgets, HUD, level-up cards, and menu screens."""
from ui.widgets import Button, Slider
from ui.upgrade_screen import UpgradeScreen
from ui.screens import (
    MainMenu,
    CampaignScreen,
    SettingsScreen,
    CharacterScreen,
    SkinShopScreen,
    LobbyScreen,
    campaign_target_wave,
)

CampaignMenu = CampaignScreen
SettingsMenu = SettingsScreen
CharacterSelectMenu = CharacterScreen
SkinShopMenu = SkinShopScreen
LobbyMenu = LobbyScreen

__all__ = [
    "Button",
    "Slider",
    "UpgradeScreen",
    "MainMenu",
    "CampaignScreen",
    "SettingsScreen",
    "CharacterScreen",
    "SkinShopScreen",
    "LobbyScreen",
    "CampaignMenu",
    "SettingsMenu",
    "CharacterSelectMenu",
    "SkinShopMenu",
    "LobbyMenu",
    "campaign_target_wave",
]
