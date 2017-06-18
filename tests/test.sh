cd $(dirname $0)

echo "Testing using Python 2..."
python2 python_tests.py
echo ""
echo "Testing using Python 3..."
python3 python_tests.py
