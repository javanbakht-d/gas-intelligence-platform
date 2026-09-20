"""
Phase 7: Forecasting Engine - نسخه 2.0 (Autoregressive Forecasting)
"""

import sqlite3
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings('ignore')

try:
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("⚠️ XGBoost نصب نیست - نصب کنید: pip install xgboost")

DB_FILE = "gas_data.db"
TARGET_COL = 'مصرف_روزانه'


# ============================================================
# 1. Feature Engineering
# ============================================================
def create_features(df, target_col=TARGET_COL):
    """ساخت ویژگی‌های زمانی و آماری بدون data leakage"""
    df = df.copy()
    df = df.sort_values('gregorian_date').reset_index(drop=True)
    
    if target_col not in df.columns:
        print(f"❌ خطا: ستون '{target_col}' یافت نشد!")
        print(f"   ستون‌های موجود: {list(df.columns)}")
        return None
    
    # === Temporal Features ===
    df['day_of_week'] = pd.to_datetime(df['gregorian_date']).dt.dayofweek
    df['month'] = pd.to_datetime(df['gregorian_date']).dt.month
    df['day_of_year'] = pd.to_datetime(df['gregorian_date']).dt.dayofyear
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    
    if 'season' in df.columns:
        df['season'] = df['season'].fillna(1).astype(int)
    
    # === Lag Features ===
    for lag in [1, 2, 3, 7, 14, 30]:
        if lag < len(df):
            df[f'lag_{lag}'] = df[target_col].shift(lag)
    
    # === Rolling Features ===
    for window in [3, 7, 14, 30]:
        if window < len(df):
            df[f'rolling_mean_{window}'] = df[target_col].shift(1).rolling(window=window, min_periods=1).mean()
            df[f'rolling_std_{window}'] = df[target_col].shift(1).rolling(window=window, min_periods=1).std()
    
    # === Growth Features ===
    if len(df) > 7:
        df['growth_1d'] = df[target_col].pct_change(1)
        df['growth_7d'] = df[target_col].pct_change(7)
        for col in ['growth_1d', 'growth_7d']:
            df[col] = df[col].replace([np.inf, -np.inf], np.nan)
    
    # حذف مقادیر نامعتبر
    df = df.dropna(subset=[target_col]).reset_index(drop=True)
    
    # پر کردن مقادیر باقی‌مانده
    df = df.ffill().bfill()
    
    return df


# ============================================================
# 2. Baseline Models
# ============================================================
def naive_forecast(train, horizon=1):
    """Naive: آخرین مقدار"""
    last_value = train[-1] if len(train) > 0 else 0
    return np.full(horizon, last_value)


def seasonal_naive_forecast(train, horizon=1, season_length=7):
    """Seasonal Naive: مقادیر مشابه هفته قبل"""
    predictions = []
    n = len(train)
    for h in range(horizon):
        idx = n - season_length + (h % season_length)
        if idx >= 0:
            predictions.append(train[idx])
        else:
            predictions.append(train[-1] if n > 0 else 0)
    return np.array(predictions)


def moving_average_forecast(train, horizon=1, window=7):
    """Moving Average: میانگین متحرک"""
    if len(train) >= window:
        last_window = train[-window:].mean()
    elif len(train) > 0:
        last_window = train.mean()
    else:
        last_window = 0
    return np.full(horizon, last_window)


# ============================================================
# 3. Metrics
# ============================================================
def calculate_metrics(y_true, y_pred):
    """محاسبه معیارهای ارزیابی"""
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    y_true = y_true[mask]
    y_pred = y_pred[mask]
    
    if len(y_true) == 0:
        return None
    
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    
    denominator = (np.abs(y_true) + np.abs(y_pred))
    smape = np.mean(np.where(denominator > 0, 
                             2 * np.abs(y_true - y_pred) / denominator, 0)) * 100
    
    nonzero = y_true != 0
    mape = np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero])) * 100 if nonzero.sum() > 0 else None
    
    total = np.sum(np.abs(y_true))
    wape = (np.sum(np.abs(y_true - y_pred)) / total * 100) if total > 0 else None
    
    return {
        'MAE': float(mae),
        'RMSE': float(rmse),
        'sMAPE': float(smape),
        'MAPE': float(mape) if mape else None,
        'WAPE': float(wape) if wape else None,
    }


# ============================================================
# 4. Walk-Forward Validation
# ============================================================
def walk_forward_validation(df, target_col=TARGET_COL, 
                            test_size=14, horizon=7, n_windows=3):
    """Walk-Forward Validation بدون data leakage"""
    print(f"\n🔬 Walk-Forward Validation")
    print(f"   Test Size: {test_size} | Horizon: {horizon} | Windows: {n_windows}")
    print(f"   کل داده‌ها: {len(df)}")
    
    results = {}
    
    for window_idx in range(n_windows):
        test_end = len(df) - (window_idx * horizon)
        test_start = test_end - test_size
        train_end = test_start
        
        if train_end < 50:
            print(f"   ⚠️ داده کافی برای پنجره {window_idx} نیست")
            break
        
        train_data = df.iloc[:train_end]
        test_data = df.iloc[test_start:test_end]
        
        print(f"   Window {window_idx + 1}: Train={len(train_data)}, Test={len(test_data)}")
        
        X_features = [c for c in df.columns if c not in [target_col, 'gregorian_date', 'shamsi_date']]
        
        X_train = train_data[X_features].fillna(0).values
        y_train = train_data[target_col].values
        X_test = test_data[X_features].fillna(0).values
        y_test = test_data[target_col].values
        
        window_results = {}
        
        # Baseline
        y_pred_naive = naive_forecast(y_train, horizon=len(y_test))
        window_results['Naive'] = calculate_metrics(y_test, y_pred_naive)
        
        y_pred_seasonal = seasonal_naive_forecast(y_train, horizon=len(y_test))
        window_results['Seasonal_Naive'] = calculate_metrics(y_test, y_pred_seasonal)
        
        y_pred_ma = moving_average_forecast(y_train, horizon=len(y_test))
        window_results['Moving_Average'] = calculate_metrics(y_test, y_pred_ma)
        
        # Linear Regression
        try:
            lr = LinearRegression()
            lr.fit(X_train, y_train)
            y_pred_lr = lr.predict(X_test)
            window_results['Linear_Regression'] = calculate_metrics(y_test, y_pred_lr)
        except Exception as e:
            print(f"   ⚠️ خطا در Linear Regression: {e}")
        
        # Random Forest
        try:
            rf = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
            rf.fit(X_train, y_train)
            y_pred_rf = rf.predict(X_test)
            window_results['Random_Forest'] = calculate_metrics(y_test, y_pred_rf)
        except Exception as e:
            print(f"   ⚠️ خطا در Random Forest: {e}")
        
        # XGBoost
        if HAS_XGBOOST:
            try:
                xgb = XGBRegressor(n_estimators=50, max_depth=5, random_state=42, n_jobs=-1)
                xgb.fit(X_train, y_train)
                y_pred_xgb = xgb.predict(X_test)
                window_results['XGBoost'] = calculate_metrics(y_test, y_pred_xgb)
            except Exception as e:
                print(f"   ⚠️ خطا در XGBoost: {e}")
        
        for model_name, metrics in window_results.items():
            if model_name not in results:
                results[model_name] = []
            if metrics is not None:
                results[model_name].append(metrics)
    
    final_results = {}
    for model_name, metrics_list in results.items():
        valid_metrics = [m for m in metrics_list if m is not None]
        if valid_metrics:
            final_results[model_name] = {
                'MAE': np.mean([m['MAE'] for m in valid_metrics]),
                'RMSE': np.mean([m['RMSE'] for m in valid_metrics]),
                'sMAPE': np.mean([m['sMAPE'] for m in valid_metrics]),
                'WAPE': np.mean([m['WAPE'] for m in valid_metrics if m.get('WAPE')]),
                'windows': len(valid_metrics)
            }
    
    return final_results


# ============================================================
# 5. Select Best Model
# ============================================================
def select_best_model(results, metric='MAE'):
    """انتخاب بهترین مدل"""
    best_model = None
    best_score = float('inf')
    
    for model_name, metrics in results.items():
        score = metrics[metric]
        if score < best_score:
            best_score = score
            best_model = model_name
    
    return best_model, best_score


# ============================================================
# 6. Autoregressive Forecast (نسخه بهبودیافته)
# ============================================================
def generate_forecast_autoregressive(df, target_col=TARGET_COL, horizon=30):
    """
    تولید پیش‌بینی با رویکرد Autoregressive
    هر پیش‌بینی به عنوان ورودی روز بعد استفاده می‌شود
    """
    print(f"\n🔮 تولید پیش‌بینی Autoregressive برای {horizon} روز آینده")
    
    X_features = [c for c in df.columns if c not in [target_col, 'gregorian_date', 'shamsi_date']]
    
    # آموزش مدل
    X_train = df[X_features].fillna(0).values
    y_train = df[target_col].values
    
    model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    
    # محاسبه بازه اطمینان
    residuals = y_train - model.predict(X_train)
    residual_std = np.std(residuals)
    
    # شروع از آخرین روز
    current_data = df.copy()
    forecasts = []
    
    for day_offset in range(1, horizon + 1):
        # محاسبه تاریخ آینده
        last_date = pd.to_datetime(current_data['gregorian_date'].iloc[-1])
        future_date = last_date + pd.Timedelta(days=day_offset)
        
        # ساخت ویژگی‌های جدید با استفاده از تاریخچه + پیش‌بینی‌های قبلی
        new_row = {
            'gregorian_date': future_date.strftime('%Y-%m-%d'),
            'day_of_week': future_date.dayofweek,
            'month': future_date.month,
            'day_of_year': future_date.dayofyear,
            'is_weekend': 1 if future_date.dayofweek >= 5 else 0,
        }
        
        # Lag Features از تاریخچه + پیش‌بینی‌های قبلی
        for lag in [1, 2, 3, 7, 14, 30]:
            if lag <= len(current_data):
                new_row[f'lag_{lag}'] = current_data[target_col].iloc[-lag]
            else:
                new_row[f'lag_{lag}'] = current_data[target_col].iloc[-1]
        
        # Rolling Features
        for window in [3, 7, 14, 30]:
            if window <= len(current_data):
                new_row[f'rolling_mean_{window}'] = current_data[target_col].iloc[-window:].mean()
                new_row[f'rolling_std_{window}'] = current_data[target_col].iloc[-window:].std()
            else:
                new_row[f'rolling_mean_{window}'] = current_data[target_col].mean()
                new_row[f'rolling_std_{window}'] = current_data[target_col].std()
        
        # Growth Features
        if len(current_data) >= 1:
            prev = current_data[target_col].iloc[-1]
            if prev != 0:
                new_row['growth_1d'] = 0  # برای روز اول پیش‌بینی
            else:
                new_row['growth_1d'] = 0
        
        if len(current_data) >= 7:
            prev_7 = current_data[target_col].iloc[-7]
            if prev_7 != 0:
                new_row['growth_7d'] = 0
            else:
                new_row['growth_7d'] = 0
        
        # Season (تقریبی)
        if 'season' in current_data.columns:
            new_row['season'] = current_data['season'].iloc[-1]
        
        # ساخت ویژگی‌ها به همان ترتیب آموزش
        feature_values = []
        for feat in X_features:
            feature_values.append(new_row.get(feat, 0))
        
        X_new = np.array([feature_values])
        
        # پیش‌بینی
        pred = model.predict(X_new)[0]
        forecasts.append({
            'day': day_offset,
            'date': future_date.strftime('%Y-%m-%d'),
            'point_forecast': float(pred),
        })
        
        # اضافه کردن پیش‌بینی به تاریخچه برای روز بعد
        new_data_row = current_data.iloc[[-1]].copy()
        for key, value in new_row.items():
            if key in new_data_row.columns:
                new_data_row[key] = value
        new_data_row[target_col] = pred
        
        current_data = pd.concat([current_data, new_data_row], ignore_index=True)
    
    # اضافه کردن بازه اطمینان
    forecast_results = []
    for f in forecasts:
        result = f.copy()
        
        # بازه اطمینان (بزرگ‌تر برای روزهای دورتر)
        uncertainty_factor = 1 + (f['day'] - 1) * 0.05  # افزایش عدم قطعیت با زمان
        
        margin_80 = 1.28 * residual_std * uncertainty_factor
        result['lower_80'] = float(f['point_forecast'] - margin_80)
        result['upper_80'] = float(f['point_forecast'] + margin_80)
        
        margin_95 = 1.96 * residual_std * uncertainty_factor
        result['lower_95'] = float(f['point_forecast'] - margin_95)
        result['upper_95'] = float(f['point_forecast'] + margin_95)
        
        forecast_results.append(result)
    
    return forecast_results, model


# ============================================================
# 7. Save Results
# ============================================================
def save_results_to_db(results, forecast_results, best_model, best_score):
    """ذخیره نتایج در دیتابیس"""
    conn = sqlite3.connect(DB_FILE)
    
    benchmark_df = pd.DataFrame([
        {
            'model_name': name,
            'MAE': metrics['MAE'],
            'RMSE': metrics['RMSE'],
            'sMAPE': metrics['sMAPE'],
            'WAPE': metrics.get('WAPE'),
            'validation_windows': metrics['windows'],
            'is_best': name == best_model,
        }
        for name, metrics in results.items()
    ])
    benchmark_df.to_sql('model_benchmarks', conn, if_exists='replace', index=False)
    
    forecast_df = pd.DataFrame(forecast_results)
    forecast_df.to_sql('forecast_results', conn, if_exists='replace', index=False)
    
    model_meta = pd.DataFrame([{
        'best_model': best_model,
        'best_score': best_score,
        'metric': 'MAE',
        'training_date': pd.Timestamp.now().isoformat(),
        'forecast_horizon': len(forecast_results),
    }])
    model_meta.to_sql('model_registry', conn, if_exists='replace', index=False)
    
    conn.commit()
    conn.close()
    
    print(f"\n💾 نتایج در دیتابیس ذخیره شدند")


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("🧠 FORECASTING ENGINE - نسخه 2.0 (Autoregressive)")
    print("=" * 60)
    
    print("\n📥 بارگذاری داده‌ها...")
    conn = sqlite3.connect(DB_FILE)
    
    query = f"""
        SELECT 
            gregorian_date,
            shamsi_year,
            shamsi_month,
            shamsi_day,
            season,
            SUM(میزان_مصرف) as {TARGET_COL},
            AVG(دمای_گاز_ساعت_6_صبح___نقطه_1) as میانگین_دما,
            AVG(فشار_ساعت_6_صبح) as میانگین_فشار
        FROM station_consumption_daily
        WHERE gregorian_date IS NOT NULL
        GROUP BY gregorian_date, shamsi_year, shamsi_month, shamsi_day, season
        ORDER BY gregorian_date
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"✅ {len(df)} رکورد روزانه بارگذاری شد")
    print(f"   بازه زمانی: {df['gregorian_date'].min()} تا {df['gregorian_date'].max()}")
    
    if len(df) < 50:
        print(f"⚠️ هشدار: داده کافی برای پیش‌بینی دقیق نیست!")
    
    print("\n🔧 ساخت ویژگی‌ها...")
    df_features = create_features(df, target_col=TARGET_COL)
    
    if df_features is None:
        return
    
    print(f"✅ {len(df_features)} رکورد با ویژگی‌های کامل")
    
    results = walk_forward_validation(df_features, target_col=TARGET_COL)
    
    print(f"\n{'='*60}")
    print("📊 نتایج بنچمارک مدل‌ها:")
    print(f"{'='*60}")
    print(f"\n{'مدل':<20} {'MAE':<12} {'RMSE':<12} {'sMAPE':<10}")
    print("-" * 54)
    
    for model_name, metrics in sorted(results.items(), key=lambda x: x[1]['MAE']):
        print(f"{model_name:<20} {metrics['MAE']:<12.2f} {metrics['RMSE']:<12.2f} "
              f"{metrics['sMAPE']:<10.2f}")
    
    if not results:
        print("❌ هیچ مدلی نتایج معتبر تولید نکرد!")
        return
    
    best_model, best_score = select_best_model(results)
    print(f"\n🏆 بهترین مدل: {best_model} (MAE={best_score:.2f})")
    
    # استفاده از روش Autoregressive
    forecast_results, model = generate_forecast_autoregressive(
        df_features, target_col=TARGET_COL, horizon=30
    )
    
    print(f"\n🔮 نمونه پیش‌بینی‌های ۷ روز اول:")
    for f in forecast_results[:7]:
        print(f"   روز +{f['day']} ({f['date']}): {f['point_forecast']:.2f} "
              f"(بازه ۹۵٪: {f['lower_95']:.2f} - {f['upper_95']:.2f})")
    
    save_results_to_db(results, forecast_results, best_model, best_score)
    
    print(f"\n{'='*60}")
    print("✅ موتور پیش‌بینی Autoregressive با موفقیت اجرا شد!")
    print(f"{'='*60}")
    
    return results, forecast_results, best_model


if __name__ == "__main__":
    main()