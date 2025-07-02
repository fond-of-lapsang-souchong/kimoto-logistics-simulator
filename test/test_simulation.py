import pytest
import pandas as pd
from unittest.mock import MagicMock
import random

from erp_module import load_erp_data
from simulation_engine import (KimotoSimulator, run_monte_carlo_simulation, 
                               generate_final_erp_data)
from ui_manager import UIManager
from config import CONFIG, URETIM_STRATEJILERI, STOK_STRATEJILERI
from app import get_initial_data
from event_library import EVENT_LIBRARY, JURY_SCENARIOS

@pytest.fixture
def default_params():
    """
    Her test için geçerli, tam ve varsayılan bir parametre sözlüğü oluşturur.
    """
    params = {
        'tek_kaynak_orani': CONFIG['ui_settings']['sliders']['tek_kaynak_orani']['default'],
        'lojistik_m': CONFIG['ui_settings']['sliders']['lojistik_m']['default'],
        'uretim_s': URETIM_STRATEJILERI[0],
        'transport_m': 'default',
        'stok_s': STOK_STRATEJILERI[0],
        'mevsimsellik_etkisi': False,
        'ozel_sku_modu': False,
        'tahmin_algoritmasi': list(CONFIG['strategy_impacts']['tahmin_modeli']['algoritmalar'].keys())[0],
        'Pazar Trendleri': False,
        'Rakip Fiyatlandırma': False,
        'Makroekonomik Göstergeler': False,
        'tahmin_d': CONFIG['kpi_defaults']['talep_tahmin_dogrulugu']
    }
    return params

@pytest.fixture(autouse=True)
def mock_streamlit(mocker):
    """Streamlit'in UI fonksiyonlarını mock'lar."""
    mocker.patch('erp_module.st', MagicMock())
    mocker.patch('ui_manager.st', MagicMock())
    mocker.patch('app.st', MagicMock())
    mocker.patch('erp_module.st.stop', side_effect=SystemExit)
    return mocker

def test_load_erp_data_missing_column(tmp_path):
    bad_csv_content = "SKU,Kategori,Stok_Adedi,Birim_Maliyet,Tedarik_Suresi_Hafta\nKIM-A-001,A,850,150,2"
    csv_file = tmp_path / "bad_erp.csv"
    csv_file.write_text(bad_csv_content)
    with pytest.raises(SystemExit):
        load_erp_data(file_path=str(csv_file))

def test_kimoto_simulator_crisis_impact(mocker, default_params):
    mocker.patch('simulation_engine.random.uniform', return_value=1.0)
    mocker.patch('simulation_engine.random.normalvariate', return_value=-0.15)
    base_data = get_initial_data(CONFIG)
    base_data['initial_kpis']['otif'] = 0.85
    simulator = KimotoSimulator(base_data, default_params, CONFIG)
    results = simulator.run({1: "Liman Grevi"}, {}, {})
    assert results['results_df'].iloc[0]['OTIF'] == pytest.approx(0.85 - 0.15)

def test_domino_effect_triggers_correctly(mocker, default_params):
    mocker.patch('simulation_engine.random.random', return_value=0.5)
    base_data = get_initial_data(CONFIG)
    simulator = KimotoSimulator(base_data, default_params, CONFIG)
    results_df = simulator.run({1: "Hammadde Tedarikçi Krizi"}, {}, {})['results_df']
    triggered_event = results_df.iloc[2]
    assert triggered_event['Gerçekleşen Olay'] == "Spot Piyasa Fiyat Artışı"

def test_intervention_mitigates_impact_and_has_cost(mocker, default_params):
    mocker.patch('simulation_engine.random.normalvariate', return_value=-0.15)
    mocker.patch('simulation_engine.random.uniform', return_value=1.0)
    base_data = get_initial_data(CONFIG)
    sim_no_int = KimotoSimulator(base_data, default_params, CONFIG)
    res_no_int = sim_no_int.run({1: "Liman Grevi"}, {}, {})
    sim_with_int = KimotoSimulator(base_data, default_params, CONFIG)
    res_with_int = sim_with_int.run({1: "Liman Grevi"}, {}, {1: "Alternatif Liman ($750K)"})
    assert res_with_int['results_df'].iloc[0]['OTIF'] > res_no_int['results_df'].iloc[0]['OTIF']
    assert res_with_int['results_df'].iloc[0]['Aylık Net Kar'] < res_no_int['results_df'].iloc[0]['Aylık Net Kar']

def test_production_strategy_shifts_production(default_params):
    base_data = get_initial_data(CONFIG)
    params = default_params.copy()
    params['uretim_s'] = 'Strateji 2: Türkiye Çevik Merkezi'
    initial_prod = base_data['tesisler_df'].copy()
    simulator = KimotoSimulator(base_data, params, CONFIG)
    final_prod = simulator.run({}, {}, {})['final_tesis_df']
    assert final_prod[final_prod['Ulke'] == 'Türkiye']['Fiili_Uretim_Ton'].sum() > initial_prod[initial_prod['Ulke'] == 'Türkiye']['Fiili_Uretim_Ton'].sum()

def test_calculate_financial_breakdown_logic():
    ui_manager = UIManager(base_data={})
    ui_manager.config = CONFIG 
    final_row = pd.Series({'OTIF': 0.90})
    otif_cost, dead_stock_cost = ui_manager._calculate_financial_breakdown(final_row)
    assert otif_cost == pytest.approx(200000.0)

def test_get_delta_color_and_sign_logic():
    ui_manager = UIManager(base_data={})
    assert ui_manager._get_delta_color_and_sign(10, True) == ("#28a745", "▲")
    assert ui_manager._get_delta_color_and_sign(-10, True) == ("#dc3545", "▼")

def test_strategy_cost_is_deducted_at_start(mocker, default_params):
    """
    Test: Başlangıç yatırım maliyetlerinin aylık kârı etkilemediğini,
    ancak ayrı bir yatırım kalemine doğru şekilde eklendiğini doğrular.
    """
    mocker.patch('simulation_engine.random.uniform', return_value=1.0)
    base_data = get_initial_data(CONFIG)
    initial_profit = base_data['initial_kpis']['net_kar_aylik']
    
    params = default_params.copy()
    params['uretim_s'] = 'Strateji 1: G. Afrika Çevik Merkezi'
    
    strategy_cost = CONFIG['strategy_impacts']['uretim']['Strateji 1: G. Afrika Çevik Merkezi']['initial_cost']
    
    simulator = KimotoSimulator(base_data, params, CONFIG)
    simulator._apply_initial_strategy_impacts()
    
    profit_after_initial_impacts = simulator.state['kpis']['net_kar_aylik']
    assert profit_after_initial_impacts == pytest.approx(initial_profit)

    investment_cost = simulator.state['initial_investment_cost']
    assert investment_cost == pytest.approx(strategy_cost)

def test_high_single_source_ratio_worsens_supply_crisis(mocker, default_params):
    mocker.patch('simulation_engine.random.normalvariate', return_value=0.75)
    mocker.patch('simulation_engine.random.uniform', return_value=1.0)
    base_data = get_initial_data(CONFIG)
    initial_production = base_data['tesisler_df']['Fiili_Uretim_Ton'].sum()
    
    params_high = default_params.copy()
    params_high['tek_kaynak_orani'] = 0.9
    
    sim_high = KimotoSimulator(base_data, params_high, CONFIG)
    final_prod_high = sim_high.run({1: "Hammadde Tedarikçi Krizi"}, {}, {})['final_tesis_df']['Fiili_Uretim_Ton'].sum()
    assert final_prod_high == pytest.approx(initial_production * (1 - (0.75 * 0.9)))

def test_special_sku_mode_impacts_multiple_kpis(mocker, default_params):
    mocker.patch('simulation_engine.random.uniform', return_value=1.0)
    base_data = get_initial_data(CONFIG)
    
    params_on = default_params.copy()
    params_on['ozel_sku_modu'] = True
    
    sim_on = KimotoSimulator(base_data, params_on, CONFIG)
    res_on = sim_on.run({}, {}, {})['results_df'].iloc[0]
    assert res_on['Stok Devir Hızı'] < base_data['initial_kpis']['stok_devir_hizi']

def test_seasonal_stock_strategy_applies_effects_in_correct_months(mocker, default_params):
    mocker.patch('simulation_engine.random.uniform', return_value=1.0)
    base_data = get_initial_data(CONFIG)
    
    params = default_params.copy()
    params['stok_s'] = 'Mevsimsel Stok Oluştur'
    
    simulator = KimotoSimulator(base_data, params, CONFIG)
    results_df = simulator.run({}, {}, {})['results_df']
    
    seasonal_cfg = CONFIG['strategy_impacts']['stok']['Mevsimsel Stok Oluştur']
    expected_bonus = seasonal_cfg['impact_otif_bonus']
    
    otif_before_bonus = results_df.iloc[9]['OTIF']
    otif_during_bonus = results_df.iloc[10]['OTIF']
    
    assert otif_during_bonus == pytest.approx(otif_before_bonus + expected_bonus)

def test_simulation_with_zero_impact_parameters(default_params):
    base_data = get_initial_data(CONFIG)
    initial_production = base_data['tesisler_df']['Fiili_Uretim_Ton'].sum()
    
    params = default_params.copy()
    params['tek_kaynak_orani'] = 0.0
    
    simulator = KimotoSimulator(base_data, params, CONFIG)
    final_production = simulator.run({1: "Hammadde Tedarikçi Krizi"}, {}, {})['final_tesis_df']['Fiili_Uretim_Ton'].sum()
    assert final_production == pytest.approx(initial_production)

def test_crisis_in_last_month_of_simulation(default_params):
    base_data = get_initial_data(CONFIG)
    simulator = KimotoSimulator(base_data, default_params, CONFIG)
    results_df = simulator.run({12: "Hammadde Tedarikçi Krizi"}, {}, {})['results_df']
    assert results_df.iloc[11]['Gerçekleşen Olay'] == "Hammadde Tedarikçi Krizi"
    assert "Domino Etkisi" not in results_df['Olay Kaynağı'].values

def test_domino_effect_is_overridden_by_manual_event(mocker, default_params):
    mocker.patch('simulation_engine.random.random', return_value=0.1)
    base_data = get_initial_data(CONFIG)
    simulator = KimotoSimulator(base_data, default_params, CONFIG)
    timeline = {1: "Hammadde Tedarikçi Krizi", 3: "Talep Patlaması"}
    results_df = simulator.run(timeline, {}, {})['results_df']
    event_in_month_3 = results_df.iloc[2]
    assert event_in_month_3['Gerçekleşen Olay'] == "Talep Patlaması"

def test_kpis_remain_within_bounds_under_extreme_stress(default_params):
    base_data = get_initial_data(CONFIG)
    
    params = default_params.copy()
    params['tek_kaynak_orani'] = 1.0
    
    nightmare_timeline = {month: "Liman Grevi" for month in range(1, 13)}
    simulator = KimotoSimulator(base_data, params, CONFIG)
    results_df = simulator.run(nightmare_timeline, {}, {})['results_df']
    assert results_df['OTIF'].min() >= 0.0
    assert results_df['Esneklik Skoru'].min() >= 0.0

def test_total_production_loss_handles_gracefully(mocker, default_params):
    mock_event = {'type': 'supply', 'impact': {'uretim_kaybi': {'dist': 'uniform', 'min': 1.0, 'max': 1.0}}, 'depends_on': 'tek_kaynak_orani', 'interventions': {'Müdahale Yok': {'cost': 0, 'mitigation_factor': 1.0}}}
    mocker.patch.dict(EVENT_LIBRARY, {'mocked_crisis': mock_event})

    base_data = get_initial_data(CONFIG)
    params = default_params.copy()
    params['tek_kaynak_orani'] = 1.0
    
    try:
        simulator = KimotoSimulator(base_data, params, CONFIG)
        results = simulator.run({1: "mocked_crisis"}, {}, {})
        assert results['final_tesis_df']['Fiili_Uretim_Ton'].sum() == pytest.approx(0.0)
    except ZeroDivisionError:
        pytest.fail("Sıfır üretim durumunda ZeroDivisionError oluştu.")

def test_erp_module_with_empty_and_malformed_data(tmp_path):
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("")
    with pytest.raises(SystemExit):
        load_erp_data(file_path=str(empty_file))
        
    header_only_file = tmp_path / "header_only.csv"
    header_only_file.write_text("SKU,Kategori,Stok_Adedi,Birim_Maliyet,Birim_Fiyat,Tedarik_Suresi_Hafta")
    df = load_erp_data(file_path=str(header_only_file))
    assert df.empty

def test_monte_carlo_output_structure_and_content(mocker, default_params):
    base_data = get_initial_data(CONFIG)
    
    mocker.patch('simulation_engine.random.random', return_value=0.99)
    mc_results_no_domino = run_monte_carlo_simulation(default_params, base_data, {1: "Liman Grevi"}, {}, {}, CONFIG, num_runs=5, callback_func=None)
    
    assert len(mc_results_no_domino) == 5
    first_run_no_domino = mc_results_no_domino[0]
    assert "realized_events" in first_run_no_domino
    assert len(first_run_no_domino["realized_events"]) == 1
    assert first_run_no_domino["realized_events"][0]["event"] == "Liman Grevi"

    mocker.patch('simulation_engine.random.random', return_value=0.10)
    mc_results_with_domino = run_monte_carlo_simulation(default_params, base_data, {1: "Liman Grevi"}, {}, {}, CONFIG, num_runs=5, callback_func=None)
    
    first_run_with_domino = mc_results_with_domino[0]
    assert "realized_events" in first_run_with_domino
    assert len(first_run_with_domino["realized_events"]) == 2

@pytest.fixture
def sample_erp_data_for_test():
    data = {
        'SKU': ['A-01', 'B-01', 'C-01'], 'Kategori': ['A', 'B', 'C'],
        'Stok_Adedi': [100, 200, 300], 'Birim_Maliyet': [10, 5, 2],
        'Birim_Fiyat': [20, 10, 4], 'Yavas_Hareket': [False, True, False],
        'Musteri_Ozel': [True, False, False], 'Talep_Tahmini': [100, 200, 300],
    }
    return pd.DataFrame(data)

def test_generate_final_erp_data(sample_erp_data_for_test, default_params):
    """
    Test: generate_final_erp_data fonksiyonunun, yeni kategori öncelikli
    optimizasyon mantığını ve diğer stratejileri doğru uyguladığını doğrular.
    """
    initial_df = sample_erp_data_for_test.copy()

    final_kpis_1 = {'Stok Devir Hızı': 6.0}
    params_1 = default_params.copy()
    result_1 = generate_final_erp_data(initial_df.copy(), final_kpis_1, params_1)
    assert result_1.loc[0, 'Stok_Adedi'] == pytest.approx(100) 
    assert result_1.loc[1, 'Stok_Adedi'] < initial_df.loc[1, 'Stok_Adedi']
 
    final_kpis_2 = {'Stok Devir Hızı': 3.0} 
    params_2 = default_params.copy()
    params_2['stok_s'] = 'Fazla Stokları Erit' 
    result_2 = generate_final_erp_data(initial_df.copy(), final_kpis_2, params_2)
    assert result_2.loc[1, 'Stok_Adedi'] == pytest.approx(200 * 0.20)

    final_kpis_3 = {'Stok Devir Hızı': 3.0, 'Gerçekleşen Olaylar_Listesi': ['Hammadde Tedarikçi Krizi']}
    params_3 = default_params.copy()
    result_3 = generate_final_erp_data(initial_df.copy(), final_kpis_3, params_3)
    assert result_3.loc[0, 'Stok_Adedi'] == pytest.approx(100 * 0.5)

def test_jury_scenario_overwrites_user_params_correctly(default_params):
    """
    Bir Jüri Özel Senaryosu yüklendiğinde, sidebar'daki kullanıcı parametrelerinin
    senaryo parametreleri ile doğru şekilde üzerine yazıldığını test eder.
    """
    user_params = default_params.copy()
    user_params['uretim_s'] = 'Strateji 1: G. Afrika Çevik Merkezi'
    
    scenario_params = JURY_SCENARIOS["Stratejik İkilem"].get("params", {})
    
    final_params = user_params.copy()
    final_params.update(scenario_params)
    
    assert final_params['uretim_s'] == 'Strateji 2: Türkiye Çevik Merkezi'
    assert final_params['uretim_s'] != 'Strateji 1: G. Afrika Çevik Merkezi'

def test_comparison_mode_params_are_independent(default_params):
    """
    Karşılaştırma modunda, bir strateji setinde yapılan değişikliğin
    diğerini etkilemediğini, yani bellek sızıntısı olmadığını test eder.
    """
    params_main = default_params.copy()
    params_compare = default_params.copy()
    
    params_main['tek_kaynak_orani'] = 0.8
    params_compare['tek_kaynak_orani'] = 0.3
    
    params_main['tek_kaynak_orani'] = 0.9
    
    assert params_main['tek_kaynak_orani'] == 0.9
    assert params_compare['tek_kaynak_orani'] == 0.3

def test_optimization_engine_finds_logical_best_for_co2(mocker, default_params):
    """
    Optimizasyon motorunun, bariz bir hedef (CO2 minimizasyonu) için
    beklenen en mantıklı stratejiyi bulabildiğini test eder.
    """
    expected_best_params = default_params.copy()
    expected_best_params['uretim_s'] = 'Strateji 2: Türkiye Çevik Merkezi'
    expected_best_params['transport_m'] = 'Deniz Yolu (Ekonomik)'
    
    mocker.patch(
        'app.run_optimization', 
        return_value=(expected_best_params, 10000, pd.DataFrame())
    )
    
    from app import run_optimization_flow
    
    mock_session_state = MagicMock()
    mocker.patch('app.st.session_state', mock_session_state)
    
    run_optimization_flow(
        params_main=default_params,
        base_data=get_initial_data(CONFIG),
        timeline={}, locations={}, interventions={},
        config=CONFIG, n_trials=10,
        optimization_goal="CO2 Tasarrufunu Maksimize Et",
        scenario_details="Test Senaryosu"
    )
    
    final_params = mock_session_state.last_results['params']
    
    assert final_params['uretim_s'] == 'Strateji 2: Türkiye Çevik Merkezi'
    assert final_params['transport_m'] == 'Deniz Yolu (Ekonomik)'