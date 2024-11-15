#!/bin/bash

# Fichier de sortie
output_file="problematic_objects_report.csv"
if [ -f "$output_file" ]; then
    rm "$output_file"
fi

# Initialiser le fichier de sortie
echo "Commit, Branch, Object ID, Object Path, Format, Author, Date, Row Size, Size" > $output_file

# Trouver les gros objets (excepté le .pack) et les trier par taille
problematic_objects=$(git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | sed -n 's/^blob //p' | grep -v '\.pack' | sort -k2 -nr)

# Utiliser un tableau associatif pour éviter les doublons
declare -A seen_objects

# Parcourir chaque objet problématique
echo "$problematic_objects" | while read -r line; do
    object_id=$(echo $line | awk '{print $1}')
    object_size=$(echo $line | awk '{print $2}')
    object_path=$(echo $line | awk '{print $3}')
    object_format=$(echo $object_path | awk -F. '{print $NF}')

    # Trouver les commits responsables de l'objet
    commits=$(git log --all --find-object=$object_id --pretty=format:"%H")

    # Parcourir chaque commit et trouver les branches correspondantes
    for commit in $commits; do
        branches=$(git branch -r --contains $commit | sed 's/^[ \t]*//')
        for branch in $branches; do
            # Ignorer les entrées avec '->'
            if [[ "$branch" == *"->"* ]]; then
                continue
            fi
            # Obtenir l'auteur et la date du commit
            author=$(git log -1 --pretty=format:"%an" $commit)
            date=$(git log -1 --pretty=format:"%ad" --date=iso $commit)
            # Formater la taille en unités lisibles
            formatted_size=$(numfmt --to=iec-i --suffix=B $object_size)
            key="$commit,$branch,$object_id,$object_path,$object_format,$author,$date,$object_size,$formatted_size"
            if [[ -z "${seen_objects[$key]}" ]]; then
                echo "$key" >> $output_file
                seen_objects[$key]=1
            fi
        done
    done
done

echo "Report generated: $output_file"