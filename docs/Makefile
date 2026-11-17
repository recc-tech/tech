bin/bilingual-lyrics.svg: bin/bilingual-lyrics.pdf
	pdftocairo -svg bin/bilingual-lyrics.pdf ./bilingual-lyrics.svg

bin/bilingual-lyrics.pdf: bilingual-lyrics.tex
	latexmk -pdf -outdir=bin bilingual-lyrics.tex
