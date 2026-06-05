# DHL Document Intelligence - Environment Setup
# Target: RTX 5080 (Blackwell sm_120), Windows 11, Python 3.11, CUDA 12.8
#
# Run from PowerShell:
#   cd D:\finetuning\DHL_Document_finetuning
#   .\setup_env.ps1
#
# After setup, activate with:
#   .\.training\Scripts\Activate.ps1

$ErrorActionPreference = "Stop"
$PY = "C:\Users\neetu\AppData\Local\Programs\Python\Python311\python.exe"
$pip    = ".\.training\Scripts\pip.exe"
$python = ".\.training\Scripts\python.exe"

# Step 1 - Verify Python
if (-not (Test-Path $PY)) {
    Write-Error "Python 3.11 not found at $PY. Install from python.org first."
    exit 1
}
Write-Host ""
Write-Host "[1/7] Python found:" -ForegroundColor Cyan
& $PY --version

# Step 2 - Create virtual environment
Write-Host ""
Write-Host "[2/7] Creating virtual environment .training ..." -ForegroundColor Cyan
if (Test-Path ".training") {
    Write-Host "  .training already exists - skipping creation" -ForegroundColor Yellow
} else {
    & $PY -m venv .training
    Write-Host "  .training created" -ForegroundColor Green
}

# Step 3 - Upgrade pip (must use python -m pip, not pip.exe, to upgrade pip itself)
Write-Host ""
Write-Host "[3/7] Upgrading pip, setuptools, wheel ..." -ForegroundColor Cyan
& $python -m pip install --upgrade pip setuptools wheel

# Step 4 - PyTorch for CUDA 12.8 (RTX 5080 Blackwell requires torch >= 2.7)
# Use explicit +cu128 version tags to prevent pip from pulling the CPU build from PyPI
Write-Host ""
Write-Host "[4/7] Installing PyTorch 2.7.0+cu128 ..." -ForegroundColor Cyan
Write-Host "  (Large download ~2.5 GB, may take a few minutes)" -ForegroundColor Yellow
& $pip install torch==2.7.0+cu128 torchvision==0.22.0+cu128 torchaudio==2.7.0+cu128 --index-url https://download.pytorch.org/whl/cu128

# Verify CUDA
Write-Host ""
Write-Host "  Verifying CUDA ..." -ForegroundColor Yellow
& $python -c "import torch; v=torch.__version__; c=torch.cuda.is_available(); g=torch.cuda.get_device_name(0) if c else 'NONE'; print(f'  torch={v}  CUDA={c}  GPU={g}')"

# Step 5 - Unsloth
Write-Host ""
Write-Host "[5/7] Installing Unsloth + dependencies ..." -ForegroundColor Cyan
Write-Host "  (includes transformers, peft, trl, accelerate, bitsandbytes)" -ForegroundColor Yellow
& $pip install "unsloth[cu128-torch270]"

# Step 6 - Data generation + app packages
Write-Host ""
Write-Host "[6/7] Installing data generation and app packages ..." -ForegroundColor Cyan
& $pip install reportlab==4.2.5 faker==37.1.0 python-docx==1.1.2 pymupdf==1.25.5 pillow==11.2.1 gradio==5.29.1

# Step 7 - Verify all imports
Write-Host ""
Write-Host "[7/7] Verifying all imports ..." -ForegroundColor Cyan
& $python -c "
import importlib, sys

ok = []
fail = []

# Non-GPU packages - verify normally
for pkg, imp in [
    ('torch',        'torch'),
    ('transformers', 'transformers'),
    ('peft',         'peft'),
    ('trl',          'trl'),
    ('accelerate',   'accelerate'),
    ('pymupdf',      'fitz'),
    ('pillow',       'PIL'),
    ('reportlab',    'reportlab'),
    ('faker',        'faker'),
    ('gradio',       'gradio'),
    ('python-docx',  'docx'),
]:
    try:
        m = importlib.import_module(imp)
        v = getattr(m, '__version__', 'ok')
        ok.append(f'  {pkg:<14} {v}')
    except Exception as e:
        fail.append(f'  {pkg:<14} FAILED: {e}')

# Torch CUDA check
try:
    import torch
    ok.append(f'  CUDA available  {torch.cuda.is_available()}')
    if torch.cuda.is_available():
        ok.append(f'  GPU             {torch.cuda.get_device_name(0)}')
except:
    pass

# Unsloth - installed check only (requires live GPU to fully import)
try:
    import importlib.util
    spec = importlib.util.find_spec('unsloth')
    if spec:
        ok.append(f'  unsloth         installed at {spec.origin}')
    else:
        fail.append('  unsloth         NOT FOUND')
except Exception as e:
    fail.append(f'  unsloth         FAILED: {e}')

print()
for line in ok:
    print(line)
if fail:
    print()
    for line in fail:
        print(line)
    sys.exit(1)
else:
    print()
    print('  ALL PACKAGES INSTALLED OK')
    print('  (Unsloth GPU init verified at runtime when GPU is active)')
"

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "" -ForegroundColor Green
Write-Host "  Activate before every session:" -ForegroundColor Green
Write-Host "    .\.training\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "" -ForegroundColor Green
Write-Host "  Then run scripts normally:" -ForegroundColor Green
Write-Host "    python prepare_dataset_v2.py" -ForegroundColor Green
Write-Host "    python train.py" -ForegroundColor Green
Write-Host "    python evaluate_baseline.py" -ForegroundColor Green
Write-Host "    python dhl_app.py" -ForegroundColor Green
Write-Host "" -ForegroundColor Green
Write-Host "  To deactivate: deactivate" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
